from django.db import transaction
from django.db.models import Q
from rest_framework import serializers

from accounts.serializers import PublicUserSerializer
from exchanges.models import ExchangeRequest
from utilities.validators import validate_image_size

from . import services
from .isbn import InvalidISBN, to_isbn13
from .models import Book, Listing, ListingImage


class BookSerializer(serializers.ModelSerializer):
    # Wider than the column so hyphenated input is accepted before normalisation.
    isbn_13 = serializers.CharField(max_length=20)
    available_listings = serializers.IntegerField(read_only=True, default=0)
    lowest_price = serializers.DecimalField(
        max_digits=8, decimal_places=2, read_only=True, allow_null=True, default=None
    )

    class Meta:
        model = Book
        fields = [
            "id",
            "isbn_13",
            "isbn_10",
            "title",
            "subtitle",
            "authors",
            "publisher",
            "published_year",
            "edition",
            "page_count",
            "cover_url",
            "description",
            "available_listings",
            "lowest_price",
        ]
        read_only_fields = ["id", "isbn_10"]

    def validate_isbn_13(self, value):
        try:
            isbn = to_isbn13(value)
        except InvalidISBN as exc:
            raise serializers.ValidationError(str(exc)) from None

        duplicates = Book.objects.filter(isbn_13=isbn)
        if self.instance is not None:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise serializers.ValidationError("A book with this ISBN already exists.")
        return isbn


class BookSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Book
        fields = ["id", "isbn_13", "title", "authors", "edition", "cover_url"]


class ListingImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ListingImage
        fields = ["id", "image", "uploaded_at"]
        read_only_fields = ["id", "uploaded_at"]
        extra_kwargs = {"image": {"validators": [validate_image_size]}}


class ListingSerializer(serializers.ModelSerializer):
    # Sellers may only switch between these; reserved/completed are set by exchanges.
    SELLER_STATUSES = (Listing.Status.AVAILABLE, Listing.Status.WITHDRAWN)

    BOOK_DETAILS = ("title", "authors", "edition")

    book = BookSummarySerializer(read_only=True)
    # The book is named either by its catalogue entry, e.g. after an ISBN lookup, or by its
    # details, which match an existing entry or add one. Most local textbooks have no ISBN.
    book_id = serializers.PrimaryKeyRelatedField(
        queryset=Book.objects.all(), source="book", write_only=True, required=False
    )
    title = serializers.CharField(max_length=300, write_only=True, required=False)
    authors = serializers.CharField(
        max_length=500, write_only=True, required=False, allow_blank=True
    )
    edition = serializers.CharField(
        max_length=50, write_only=True, required=False, allow_blank=True
    )
    seller = PublicUserSerializer(read_only=True)
    images = ListingImageSerializer(many=True, read_only=True)
    is_owner = serializers.SerializerMethodField()

    class Meta:
        model = Listing
        fields = [
            "id",
            "book",
            "book_id",
            "title",
            "authors",
            "edition",
            "seller",
            "is_owner",
            "condition",
            "listing_type",
            "price",
            "description",
            "course_code",
            "status",
            "images",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_is_owner(self, obj) -> bool:
        return obj.seller_id == self.context["request"].user.id

    def validate_book_id(self, book):
        if self.instance is not None and book != self.instance.book:
            raise serializers.ValidationError("The book of a listing cannot be changed.")
        return book

    def validate_course_code(self, value):
        return value.strip().upper()

    def validate_status(self, value):
        if value not in self.SELLER_STATUSES:
            raise serializers.ValidationError(
                "Status can only be set to 'available' or 'withdrawn'."
            )
        if self.instance is not None and self.instance.status not in self.SELLER_STATUSES:
            raise serializers.ValidationError(
                "This listing is part of an exchange; manage it through the exchange."
            )
        return value

    def _validate_book_details(self, attrs):
        """Collects the book's details into `book_details`, which `save` turns into a book."""
        details = {
            field: " ".join(attrs.pop(field).split())
            for field in self.BOOK_DETAILS
            if field in attrs
        }
        if not details:
            if self.instance is None and "book" not in attrs:
                raise serializers.ValidationError({"title": "Give the book's title."})
            return
        if "book" in attrs:
            raise serializers.ValidationError(
                {"book_id": "Give either book_id or the book's details, not both."}
            )

        if self.instance is not None:
            current = {field: getattr(self.instance.book, field) for field in self.BOOK_DETAILS}
            details = {**current, **details}
            changed = any(details[key].casefold() != current[key].casefold() for key in current)
            if changed and self._has_active_exchange():
                raise serializers.ValidationError(
                    {
                        "title": "Students have asked for this book as it is listed. "
                        "Settle their requests before changing its details."
                    }
                )
        if not details.get("title"):
            raise serializers.ValidationError({"title": "Give the book's title."})
        attrs["book_details"] = details

    def _has_active_exchange(self):
        active = Q(status__in=ExchangeRequest.ACTIVE_STATUSES)
        return (
            self.instance.exchanges.filter(active).exists()
            or self.instance.offered_in_exchanges.filter(active).exists()
        )

    @transaction.atomic
    def save(self, **kwargs):
        details = self.validated_data.pop("book_details", None)
        if details is not None:
            kwargs["book"] = services.find_or_create_book(**details)
        return super().save(**kwargs)

    def validate(self, attrs):
        self._validate_book_details(attrs)
        listing_type = attrs.get("listing_type", getattr(self.instance, "listing_type", None))
        price = attrs.get("price", getattr(self.instance, "price", None))

        if listing_type == Listing.ListingType.SELL and not price:
            raise serializers.ValidationError(
                {"price": "A selling price above 0 is required. List free books as donations."}
            )
        if listing_type == Listing.ListingType.DONATE:
            attrs["price"] = None
        return attrs


class ViewerListingSerializer(ListingSerializer):
    """A listing as the listing endpoints return it, with the viewer's own request on it.

    Exchanges nest the plain `ListingSerializer`: their own status already says this.
    """

    has_active_request = serializers.BooleanField(
        read_only=True,
        default=False,
        help_text="The signed-in student has a pending or accepted request for this listing.",
    )

    class Meta(ListingSerializer.Meta):
        fields = [*ListingSerializer.Meta.fields, "has_active_request"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Students' names are for other students, not for anyone on the web.
        if not self.context["request"].user.is_authenticated:
            data["seller"] = None
        return data

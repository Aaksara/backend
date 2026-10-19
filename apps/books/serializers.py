from rest_framework import serializers

from apps.accounts.serializers import PublicUserSerializer
from apps.core.validators import validate_image_size

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

    def validate_image(self, image):
        return validate_image_size(image)


class ListingSerializer(serializers.ModelSerializer):
    # Sellers may only switch between these; reserved/completed are set by exchanges.
    SELLER_STATUSES = (Listing.Status.AVAILABLE, Listing.Status.WITHDRAWN)

    book = BookSummarySerializer(read_only=True)
    book_id = serializers.PrimaryKeyRelatedField(
        queryset=Book.objects.all(), source="book", write_only=True
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
            "seller",
            "is_owner",
            "condition",
            "listing_type",
            "price",
            "description",
            "course_code",
            "preferred_location",
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

    def validate_preferred_location(self, location):
        if location is not None and not location.is_active:
            raise serializers.ValidationError("This meetup location is no longer available.")
        return location

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

    def validate(self, attrs):
        listing_type = attrs.get("listing_type", getattr(self.instance, "listing_type", None))
        price = attrs.get("price", getattr(self.instance, "price", None))

        if listing_type == Listing.ListingType.SELL and not price:
            raise serializers.ValidationError(
                {"price": "A selling price above 0 is required. List free books as donations."}
            )
        if listing_type == Listing.ListingType.DONATE:
            attrs["price"] = None
        return attrs

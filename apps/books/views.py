from django.conf import settings
from django.db import transaction
from django.db.models import Count, Min, Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from apps.exchanges.services import close_pending_requests

from . import services
from .filters import ListingFilter
from .isbn import InvalidISBN, to_isbn13
from .models import Book, Listing, ListingImage
from .permissions import IsSellerOrReadOnly
from .serializers import BookSerializer, ListingImageSerializer, ListingSerializer


class BookViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Shared book catalogue. Any student can add a missing book; only staff can edit."""

    serializer_class = BookSerializer
    search_fields = ["title", "subtitle", "authors", "isbn_13", "isbn_10", "publisher"]
    ordering_fields = ["title", "published_year", "available_listings", "lowest_price"]
    filterset_fields = ["published_year"]

    def get_queryset(self):
        available = Q(listings__status=Listing.Status.AVAILABLE)
        return Book.objects.annotate(
            available_listings=Count("listings", filter=available),
            lowest_price=Min("listings__price", filter=available),
        ).order_by("title")

    def get_permissions(self):
        if self.action in ("update", "partial_update"):
            return [IsAdminUser()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        # Trust the public catalogues over the student's input when they know the ISBN,
        # so nobody can claim an edition with wrong details.
        metadata = services.fetch_book_metadata(serializer.validated_data["isbn_13"])
        serializer.save(**(metadata or {}))

    @extend_schema(
        parameters=[OpenApiParameter("isbn", str, required=True, description="ISBN-10 or 13")],
        responses={200: BookSerializer},
    )
    @action(detail=False, methods=["get"])
    def lookup(self, request):
        """Find a book by ISBN, importing it from Open Library / Google Books if unknown."""
        try:
            isbn = to_isbn13(request.query_params.get("isbn", ""))
        except InvalidISBN as exc:
            raise ValidationError({"isbn": str(exc)}) from None
        book = services.get_or_fetch_book(isbn)
        if book is None:
            return Response(
                {"detail": "No book found for this ISBN. You can add it manually."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(self.get_serializer(self.get_queryset().get(pk=book.pk)).data)


class ListingViewSet(viewsets.ModelViewSet):
    serializer_class = ListingSerializer
    permission_classes = [IsAuthenticated, IsSellerOrReadOnly]
    filterset_class = ListingFilter
    search_fields = ["book__title", "book__authors", "book__isbn_13", "course_code", "description"]
    ordering_fields = ["created_at", "price"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Listing.objects.none()
        user = self.request.user
        listings = Listing.objects.select_related(
            "book", "seller", "preferred_location"
        ).prefetch_related("images")

        if self.action == "mine":
            return listings.filter(seller=user)
        # Withdrawn listings are only visible to their seller.
        listings = listings.filter(~Q(status=Listing.Status.WITHDRAWN) | Q(seller=user))
        # Browsing defaults to what can actually be requested right now.
        if self.action == "list" and "status" not in self.request.query_params:
            listings = listings.filter(status=Listing.Status.AVAILABLE)
        return listings

    def perform_create(self, serializer):
        serializer.save(seller=self.request.user)

    @transaction.atomic
    def perform_update(self, serializer):
        listing = serializer.save()
        if listing.status == Listing.Status.WITHDRAWN:
            close_pending_requests(listing)

    @transaction.atomic
    def perform_destroy(self, instance):
        if instance.status == Listing.Status.RESERVED:
            raise ValidationError(
                "This listing has an accepted exchange. Cancel the exchange before deleting."
            )
        if instance.status == Listing.Status.COMPLETED:
            raise ValidationError("Completed listings are kept as exchange history.")
        if instance.exchanges.exists() or instance.offered_in_exchanges.exists():
            # Keep the exchange history intact for the other party; just hide the listing.
            instance.status = Listing.Status.WITHDRAWN
            instance.save(update_fields=["status", "updated_at"])
            close_pending_requests(instance)
            return
        instance.delete()

    @action(detail=False, methods=["get"])
    def mine(self, request):
        """All of the current user's listings, in any status."""
        return self.list(request)

    @extend_schema(request={"multipart/form-data": ListingImageSerializer})
    @action(
        detail=True,
        methods=["post"],
        parser_classes=[MultiPartParser, FormParser],
        serializer_class=ListingImageSerializer,
    )
    def images(self, request, pk=None):
        listing = self.get_object()
        if listing.images.count() >= settings.MAX_LISTING_IMAGES:
            raise ValidationError(
                f"A listing can have at most {settings.MAX_LISTING_IMAGES} images."
            )
        serializer = ListingImageSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save(listing=listing)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["delete"], url_path=r"images/(?P<image_id>\d+)")
    def delete_image(self, request, pk=None, image_id=None):
        listing = self.get_object()
        image = get_object_or_404(ListingImage, pk=image_id, listing=listing)
        image.image.delete(save=False)
        image.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

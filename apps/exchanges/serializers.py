from django.utils import timezone
from rest_framework import serializers

from apps.accounts.serializers import PublicUserSerializer
from apps.books.models import Listing
from apps.books.serializers import ListingSerializer

from .models import ExchangeRequest, MeetupLocation


class MeetupLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = MeetupLocation
        fields = ["id", "name", "description"]


class ExchangeRequestSerializer(serializers.ModelSerializer):
    requester = PublicUserSerializer(read_only=True)
    seller = PublicUserSerializer(source="listing.seller", read_only=True)
    listing_detail = ListingSerializer(source="listing", read_only=True)
    offered_listing_detail = ListingSerializer(source="offered_listing", read_only=True)
    meetup_location_detail = MeetupLocationSerializer(source="meetup_location", read_only=True)
    role = serializers.SerializerMethodField()

    class Meta:
        model = ExchangeRequest
        fields = [
            "id",
            "listing",
            "listing_detail",
            "requester",
            "seller",
            "role",
            "offered_price",
            "offered_listing",
            "offered_listing_detail",
            "message",
            "status",
            "meetup_location",
            "meetup_location_detail",
            "meetup_time",
            "responded_at",
            "completed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "status",
            "meetup_location",
            "meetup_time",
            "responded_at",
            "completed_at",
            "created_at",
            "updated_at",
        ]

    def get_role(self, obj) -> str:
        user = self.context["request"].user
        return "seller" if obj.listing.seller_id == user.id else "requester"

    def validate(self, attrs):
        user = self.context["request"].user
        listing = attrs["listing"]
        offered = attrs.get("offered_listing")

        if listing.seller_id == user.id:
            raise serializers.ValidationError({"listing": "You cannot request your own listing."})
        if listing.status != Listing.Status.AVAILABLE:
            raise serializers.ValidationError({"listing": "This listing is not available."})
        if ExchangeRequest.objects.filter(
            listing=listing, requester=user, status__in=ExchangeRequest.ACTIVE_STATUSES
        ).exists():
            raise serializers.ValidationError(
                {"listing": "You already have an active request for this listing."}
            )

        if offered is not None:
            if offered.seller_id != user.id:
                raise serializers.ValidationError(
                    {"offered_listing": "You can only offer your own listings."}
                )
            if offered.status != Listing.Status.AVAILABLE:
                raise serializers.ValidationError(
                    {"offered_listing": "The offered listing is not available."}
                )

        if listing.listing_type == Listing.ListingType.EXCHANGE and offered is None:
            raise serializers.ValidationError(
                {"offered_listing": "This listing is exchange-only; offer one of your books."}
            )
        if listing.listing_type == Listing.ListingType.SELL and attrs.get("offered_price") is None:
            attrs["offered_price"] = listing.price
        if listing.listing_type == Listing.ListingType.DONATE:
            attrs["offered_price"] = None
        return attrs


class AcceptExchangeSerializer(serializers.Serializer):
    meetup_location = serializers.PrimaryKeyRelatedField(
        queryset=MeetupLocation.objects.filter(is_active=True)
    )
    meetup_time = serializers.DateTimeField()

    def validate_meetup_time(self, value):
        if value <= timezone.now():
            raise serializers.ValidationError("Meetup time must be in the future.")
        return value

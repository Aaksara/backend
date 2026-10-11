from rest_framework import serializers

from apps.accounts.serializers import PublicUserSerializer
from apps.books.models import Listing
from apps.books.serializers import BookSummarySerializer

from .models import MAX_MESSAGE_LENGTH, Conversation, Message


class MessageSerializer(serializers.ModelSerializer):
    body = serializers.CharField(max_length=MAX_MESSAGE_LENGTH)

    class Meta:
        model = Message
        fields = ["id", "conversation", "sender", "body", "created_at", "read_at"]
        read_only_fields = ["id", "conversation", "sender", "created_at", "read_at"]


class ConversationListingSerializer(serializers.ModelSerializer):
    book = BookSummarySerializer(read_only=True)

    class Meta:
        model = Listing
        fields = ["id", "book", "price", "listing_type", "status"]


class ConversationSerializer(serializers.ModelSerializer):
    listing = serializers.PrimaryKeyRelatedField(
        queryset=Listing.objects.exclude(status=Listing.Status.WITHDRAWN), write_only=True
    )
    listing_detail = ConversationListingSerializer(source="listing", read_only=True)
    buyer = PublicUserSerializer(read_only=True)
    seller = PublicUserSerializer(read_only=True)
    last_message = MessageSerializer(read_only=True, allow_null=True)
    unread_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Conversation
        fields = [
            "id",
            "listing",
            "listing_detail",
            "buyer",
            "seller",
            "last_message",
            "unread_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_listing(self, listing):
        if listing.seller_id == self.context["request"].user.id:
            raise serializers.ValidationError(
                "You cannot start a conversation on your own listing."
            )
        return listing

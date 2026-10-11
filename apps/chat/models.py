from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel

MAX_MESSAGE_LENGTH = 2000


class Conversation(TimeStampedModel):
    """A private thread between a prospective buyer and the seller about one listing."""

    listing = models.ForeignKey(
        "books.Listing", on_delete=models.CASCADE, related_name="conversations"
    )
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="buyer_conversations"
    )
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="seller_conversations"
    )
    last_message = models.ForeignKey(
        "Message", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(fields=["listing", "buyer"], name="one_conversation_per_buyer")
        ]

    def __str__(self):
        return f"Conversation {self.pk} on listing {self.listing_id}"

    def has_participant(self, user) -> bool:
        return user.id in (self.buyer_id, self.seller_id)

    def other_participant_id(self, user) -> int:
        return self.seller_id if user.id == self.buyer_id else self.buyer_id


class Message(models.Model):
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages"
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="messages_sent"
    )
    body = models.TextField(max_length=MAX_MESSAGE_LENGTH)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.sender_id}: {self.body[:40]}"

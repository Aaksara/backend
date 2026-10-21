"""Sending and reading messages. Clients poll the REST API for new messages."""

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from .models import Conversation, Message


def conversations_for(user):
    """The user's conversations, most recently active first, with their unread counts."""
    unread = Q(messages__read_at__isnull=True) & ~Q(messages__sender=user)
    return (
        Conversation.objects.filter(Q(buyer=user) | Q(seller=user))
        .select_related("listing__book", "buyer", "seller", "last_message")
        .annotate(unread_count=Count("messages", filter=unread))
        .order_by("-updated_at")
    )


def unread_total(user) -> int:
    """Messages from others, in any of the user's conversations, that they have not read."""
    return (
        Message.objects.filter(
            Q(conversation__buyer=user) | Q(conversation__seller=user), read_at__isnull=True
        )
        .exclude(sender=user)
        .count()
    )


def open_conversation(listing, buyer) -> tuple[Conversation, bool]:
    """The conversation between a listing's seller and this buyer, started if needed."""
    return Conversation.objects.get_or_create(
        listing=listing, buyer=buyer, defaults={"seller": listing.seller}
    )


def send_message(conversation: Conversation, sender, body: str) -> Message:
    with transaction.atomic():
        message = Message.objects.create(conversation=conversation, sender=sender, body=body)
        conversation.last_message = message
        conversation.save(update_fields=["last_message", "updated_at"])
    return message


def mark_read(conversation: Conversation, reader) -> int:
    """Mark the other participant's unread messages as read; returns how many changed."""
    return (
        conversation.messages.filter(read_at__isnull=True)
        .exclude(sender=reader)
        .update(read_at=timezone.now())
    )

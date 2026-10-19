"""Sending and reading messages. Clients poll the REST API for new messages."""

from django.db import transaction
from django.utils import timezone

from .models import Conversation, Message


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

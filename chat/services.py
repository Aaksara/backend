"""Sending and reading messages.

Shared by the REST API and the WebSocket consumer so every change is saved and
pushed to connected clients in exactly one way.
"""

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from django.utils import timezone

from .models import Conversation, Message
from .serializers import MessageSerializer


def conversation_group(conversation_id: int) -> str:
    return f"chat_{conversation_id}"


def user_group(user_id: int) -> str:
    return f"user_{user_id}"


def _push(group: str, event: dict) -> None:
    async_to_sync(get_channel_layer().group_send)(group, event)


def send_message(conversation: Conversation, sender, body: str) -> Message:
    with transaction.atomic():
        message = Message.objects.create(conversation=conversation, sender=sender, body=body)
        conversation.last_message = message
        conversation.save(update_fields=["last_message", "updated_at"])

    payload = dict(MessageSerializer(message).data)
    recipient_id = conversation.other_participant_id(sender)
    _push(conversation_group(conversation.pk), {"type": "chat.message", "message": payload})
    _push(user_group(recipient_id), {"type": "inbox.message", "message": payload})
    return message


def mark_read(conversation: Conversation, reader) -> int:
    """Mark the other participant's unread messages as read; returns how many changed."""
    now = timezone.now()
    updated = (
        conversation.messages.filter(read_at__isnull=True)
        .exclude(sender=reader)
        .update(read_at=now)
    )
    if updated:
        _push(
            conversation_group(conversation.pk),
            {"type": "chat.read", "reader": reader.id, "read_at": now.isoformat()},
        )
    return updated

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from . import services
from .models import Conversation
from .serializers import MessageSerializer

# Application-defined close codes (4000-4999).
UNAUTHENTICATED = 4401
FORBIDDEN = 4403


async def reject(consumer, code):
    """Close with an application code.

    Accepting first is required: closing during the handshake makes browsers see a
    generic failure (code 1006) instead of our code.
    """
    await consumer.accept()
    await consumer.close(code=code)


class ChatConsumer(AsyncJsonWebsocketConsumer):
    """Live channel for one conversation.

    Client -> server:
        {"type": "message", "body": "..."}
        {"type": "typing", "is_typing": true}
        {"type": "read"}
    Server -> client:
        {"type": "message", "message": {...}}
        {"type": "typing", "user": <id>, "is_typing": bool}
        {"type": "read", "reader": <id>, "read_at": "..."}
        {"type": "error", "detail": ...}
    """

    async def connect(self):
        self.user = self.scope["user"]
        if not self.user.is_authenticated:
            await reject(self, UNAUTHENTICATED)
            return

        conversation_id = self.scope["url_route"]["kwargs"]["conversation_id"]
        self.conversation = await self._get_conversation(conversation_id)
        if self.conversation is None:
            await reject(self, FORBIDDEN)
            return

        self.group_name = services.conversation_group(conversation_id)
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        event_type = content.get("type")
        if event_type == "message":
            await self._send_message(content)
        elif event_type == "typing":
            await self._send_typing(content)
        elif event_type == "read":
            await database_sync_to_async(services.mark_read)(self.conversation, self.user)
        else:
            await self.send_json({"type": "error", "detail": f"Unknown type '{event_type}'."})

    async def _send_message(self, content):
        serializer = MessageSerializer(data=content)
        if not serializer.is_valid():
            await self.send_json({"type": "error", "detail": serializer.errors})
            return
        await database_sync_to_async(services.send_message)(
            self.conversation, self.user, serializer.validated_data["body"]
        )

    async def _send_typing(self, content):
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "chat.typing",
                "user": self.user.id,
                "is_typing": bool(content.get("is_typing", True)),
            },
        )

    # Handlers for events sent to the group ----------------------------------------

    async def chat_message(self, event):
        await self.send_json({"type": "message", "message": event["message"]})

    async def chat_typing(self, event):
        if event["user"] != self.user.id:
            await self.send_json(
                {"type": "typing", "user": event["user"], "is_typing": event["is_typing"]}
            )

    async def chat_read(self, event):
        await self.send_json(
            {"type": "read", "reader": event["reader"], "read_at": event["read_at"]}
        )

    @database_sync_to_async
    def _get_conversation(self, conversation_id):
        conversation = Conversation.objects.filter(pk=conversation_id).first()
        if conversation and conversation.has_participant(self.user):
            return conversation
        return None


class InboxConsumer(AsyncJsonWebsocketConsumer):
    """Per-user feed of new messages across all conversations (for unread badges)."""

    async def connect(self):
        user = self.scope["user"]
        if not user.is_authenticated:
            await reject(self, UNAUTHENTICATED)
            return

        self.group_name = services.user_group(user.id)
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def inbox_message(self, event):
        await self.send_json({"type": "message", "message": event["message"]})

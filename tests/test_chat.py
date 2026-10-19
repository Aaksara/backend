import pytest
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from rest_framework_simplejwt.tokens import AccessToken

from apps.chat import consumers
from apps.chat.models import Conversation, Message
from config.asgi import application


@pytest.mark.django_db
class TestConversationAPI:
    def test_start_conversation_is_idempotent(self, client_for, seller, buyer, make_listing):
        listing = make_listing(seller)
        client = client_for(buyer)
        first = client.post("/api/conversations/", {"listing": listing.id})
        assert first.status_code == 201
        assert first.data["seller"]["id"] == seller.id
        second = client.post("/api/conversations/", {"listing": listing.id})
        assert second.status_code == 200
        assert second.data["id"] == first.data["id"]

    def test_cannot_message_yourself(self, client_for, seller, make_listing):
        listing = make_listing(seller)
        resp = client_for(seller).post("/api/conversations/", {"listing": listing.id})
        assert resp.status_code == 400

    def test_send_read_and_unread_counts(self, client_for, seller, buyer, make_listing):
        listing = make_listing(seller)
        buyer_client, seller_client = client_for(buyer), client_for(seller)
        conv_id = buyer_client.post("/api/conversations/", {"listing": listing.id}).data["id"]

        resp = buyer_client.post(f"/api/conversations/{conv_id}/messages/", {"body": " Hi! "})
        assert resp.status_code == 201
        assert resp.data["body"] == "Hi!"

        inbox = seller_client.get("/api/conversations/").data["results"]
        assert inbox[0]["unread_count"] == 1
        assert inbox[0]["last_message"]["body"] == "Hi!"

        assert seller_client.post(f"/api/conversations/{conv_id}/read/").data["marked_read"] == 1
        assert seller_client.get("/api/conversations/").data["results"][0]["unread_count"] == 0

        history = seller_client.get(f"/api/conversations/{conv_id}/messages/").data
        assert history["count"] == 1

    def test_outsiders_cannot_read(self, client_for, seller, buyer, make_user, make_listing):
        listing = make_listing(seller)
        conv_id = client_for(buyer).post("/api/conversations/", {"listing": listing.id}).data["id"]
        outsider = client_for(make_user())
        assert outsider.get(f"/api/conversations/{conv_id}/messages/").status_code == 404


def _connect(path, user=None, origin=b"http://localhost:3000"):
    headers = [(b"origin", origin)]
    if user is not None:
        headers.append((b"cookie", f"access_token={AccessToken.for_user(user)}".encode()))
    return WebsocketCommunicator(application, path, headers=headers)


@pytest.fixture
def conversation(seller, buyer, make_listing):
    listing = make_listing(seller)
    return Conversation.objects.create(listing=listing, buyer=buyer, seller=seller)


@pytest.mark.django_db(transaction=True)
class TestChatWebSocket:
    async def test_rejects_anonymous_and_outsiders(self, conversation, make_user):
        comm = _connect(f"/ws/chat/{conversation.id}/")
        await comm.connect()
        assert await comm.receive_output() == {"type": "websocket.close", "code": 4401}

        outsider = await database_sync_to_async(make_user)()
        comm = _connect(f"/ws/chat/{conversation.id}/", outsider)
        await comm.connect()
        assert await comm.receive_output() == {"type": "websocket.close", "code": 4403}

    async def test_rejects_unknown_origin(self, conversation, buyer):
        comm = _connect(f"/ws/chat/{conversation.id}/", buyer, origin=b"https://evil.example")
        connected, _ = await comm.connect()
        assert not connected

    async def test_rate_limits_messages(self, conversation, buyer, monkeypatch):
        monkeypatch.setattr(consumers, "MESSAGES_PER_MINUTE", 1)
        comm = _connect(f"/ws/chat/{conversation.id}/", buyer)
        await comm.connect()
        await comm.send_json_to({"type": "message", "body": "one"})
        assert (await comm.receive_json_from())["type"] == "message"
        await comm.send_json_to({"type": "message", "body": "two"})
        assert (await comm.receive_json_from())["type"] == "error"
        assert await database_sync_to_async(Message.objects.count)() == 1
        await comm.disconnect()

    async def test_realtime_message_typing_and_read(self, conversation, buyer, seller):
        buyer_ws = _connect(f"/ws/chat/{conversation.id}/", buyer)
        seller_ws = _connect(f"/ws/chat/{conversation.id}/", seller)
        seller_inbox = _connect("/ws/inbox/", seller)
        for ws in (buyer_ws, seller_ws, seller_inbox):
            connected, _ = await ws.connect()
            assert connected

        await buyer_ws.send_json_to({"type": "typing", "is_typing": True})
        assert await seller_ws.receive_json_from() == {
            "type": "typing",
            "user": buyer.id,
            "is_typing": True,
        }
        assert await buyer_ws.receive_nothing()  # no echo of own typing

        await buyer_ws.send_json_to({"type": "message", "body": "Still available?"})
        for ws in (buyer_ws, seller_ws, seller_inbox):
            event = await ws.receive_json_from()
            assert event["type"] == "message"
            assert event["message"]["body"] == "Still available?"
            assert event["message"]["sender"] == buyer.id

        await seller_ws.send_json_to({"type": "read"})
        event = await buyer_ws.receive_json_from()
        assert event["type"] == "read" and event["reader"] == seller.id

        msg = await database_sync_to_async(Message.objects.get)()
        assert msg.read_at is not None

        await buyer_ws.send_json_to({"type": "message", "body": "   "})
        assert (await buyer_ws.receive_json_from())["type"] == "error"

        for ws in (buyer_ws, seller_ws, seller_inbox):
            await ws.disconnect()

import pytest


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

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

    def test_unread_total_counts_every_conversation(
        self, client_for, seller, buyer, make_user, make_listing, other_book
    ):
        first = make_listing(seller)
        second = make_listing(seller, book=other_book)
        other_buyer = make_user()
        for client, listing in [(client_for(buyer), first), (client_for(other_buyer), second)]:
            conv_id = client.post("/api/conversations/", {"listing": listing.id}).data["id"]
            client.post(f"/api/conversations/{conv_id}/messages/", {"body": "Still available?"})

        assert client_for(seller).get("/api/conversations/unread/").data == {"unread": 2}
        # Your own messages are never unread for you.
        assert client_for(buyer).get("/api/conversations/unread/").data == {"unread": 0}


@pytest.mark.django_db
class TestExchangeConversation:
    def test_either_side_opens_the_same_chat(self, client_for, seller, buyer, make_listing):
        listing = make_listing(seller)
        exchange_id = client_for(buyer).post("/api/exchanges/", {"listing": listing.id}).data["id"]
        url = f"/api/exchanges/{exchange_id}/conversation/"

        # The seller can start it, though only buyers can start a chat on a listing.
        opened = client_for(seller).post(url)
        assert opened.status_code == 201
        assert opened.data["buyer"]["id"] == buyer.id
        assert opened.data["seller"]["id"] == seller.id

        again = client_for(buyer).post(url)
        assert again.status_code == 200
        assert again.data["id"] == opened.data["id"]

    def test_reuses_a_chat_the_buyer_already_started(self, client_for, seller, buyer, make_listing):
        listing = make_listing(seller)
        client = client_for(buyer)
        chat_id = client.post("/api/conversations/", {"listing": listing.id}).data["id"]
        exchange_id = client.post("/api/exchanges/", {"listing": listing.id}).data["id"]
        resp = client_for(seller).post(f"/api/exchanges/{exchange_id}/conversation/")
        assert resp.status_code == 200
        assert resp.data["id"] == chat_id

    def test_outsiders_cannot_open_it(self, client_for, seller, buyer, make_user, make_listing):
        listing = make_listing(seller)
        exchange_id = client_for(buyer).post("/api/exchanges/", {"listing": listing.id}).data["id"]
        outsider = client_for(make_user())
        assert outsider.post(f"/api/exchanges/{exchange_id}/conversation/").status_code == 404

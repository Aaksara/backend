import pytest

from books.models import Listing
from exchanges.models import ExchangeRequest

pytestmark = pytest.mark.django_db


def _request(client, listing, **extra):
    return client.post("/api/exchanges/", {"listing": listing.id, **extra})


def test_cannot_request_own_listing(client_for, seller, make_listing):
    listing = make_listing(seller)
    assert _request(client_for(seller), listing).status_code == 400


def test_one_active_request_per_listing(client_for, seller, buyer, make_listing):
    listing = make_listing(seller)
    client = client_for(buyer)
    resp = _request(client, listing)
    assert resp.status_code == 201
    assert resp.data["offered_price"] == "25.00"  # defaults to asking price
    assert _request(client, listing).status_code == 400


def test_exchange_only_listing_requires_offer(client_for, seller, buyer, make_listing, other_book):
    listing = make_listing(seller, listing_type="exchange", price=None)
    client = client_for(buyer)
    assert _request(client, listing).status_code == 400
    mine = make_listing(buyer, book=other_book)
    assert _request(client, listing, offered_listing=mine.id).status_code == 201


def test_cannot_offer_someone_elses_listing(client_for, seller, buyer, make_user, make_listing):
    listing = make_listing(seller, listing_type="exchange", price=None)
    third = make_listing(make_user())
    assert _request(client_for(buyer), listing, offered_listing=third.id).status_code == 400


def test_full_happy_path(client_for, seller, buyer, make_user, make_listing):
    listing = make_listing(seller)
    rival = make_user()
    exchange_id = _request(client_for(buyer), listing).data["id"]
    rival_id = _request(client_for(rival), listing).data["id"]
    seller_client = client_for(seller)

    # Buyer cannot accept on the seller's behalf.
    resp = client_for(buyer).post(f"/api/exchanges/{exchange_id}/accept/")
    assert resp.status_code == 403

    resp = seller_client.post(f"/api/exchanges/{exchange_id}/accept/")
    assert resp.status_code == 200, resp.data
    assert resp.data["status"] == "accepted"
    listing.refresh_from_db()
    assert listing.status == Listing.Status.RESERVED

    # Book is reserved, so the rival's request cannot also be accepted.
    resp = seller_client.post(f"/api/exchanges/{rival_id}/accept/")
    assert resp.status_code == 400
    assert resp.data == {"detail": "This listing is no longer available."}

    assert client_for(buyer).post(f"/api/exchanges/{exchange_id}/complete/").status_code == 200
    listing.refresh_from_db()
    assert listing.status == Listing.Status.COMPLETED
    assert ExchangeRequest.objects.get(pk=rival_id).status == "rejected"


def test_cancel_accepted_releases_listing(client_for, seller, buyer, make_listing):
    listing = make_listing(seller)
    exchange_id = _request(client_for(buyer), listing).data["id"]
    client_for(seller).post(f"/api/exchanges/{exchange_id}/accept/")
    assert client_for(buyer).post(f"/api/exchanges/{exchange_id}/cancel/").status_code == 200
    listing.refresh_from_db()
    assert listing.status == Listing.Status.AVAILABLE


def test_swap_reserves_and_completes_both_books(
    client_for, seller, buyer, make_listing, other_book
):
    wanted = make_listing(seller, listing_type="exchange", price=None)
    offered = make_listing(buyer, book=other_book)
    exchange_id = _request(client_for(buyer), wanted, offered_listing=offered.id).data["id"]
    client_for(seller).post(f"/api/exchanges/{exchange_id}/accept/")
    offered.refresh_from_db()
    assert offered.status == Listing.Status.RESERVED
    client_for(seller).post(f"/api/exchanges/{exchange_id}/complete/")
    offered.refresh_from_db()
    assert offered.status == Listing.Status.COMPLETED


def test_completing_swap_rejects_other_requests_offering_the_same_book(
    client_for, seller, buyer, make_user, make_listing, other_book
):
    wanted = make_listing(seller, listing_type="exchange", price=None)
    elsewhere = make_listing(make_user(), listing_type="exchange", price=None)
    offered = make_listing(buyer, book=other_book)
    buyer_client = client_for(buyer)
    swap_id = _request(buyer_client, wanted, offered_listing=offered.id).data["id"]
    other_id = _request(buyer_client, elsewhere, offered_listing=offered.id).data["id"]

    client_for(seller).post(f"/api/exchanges/{swap_id}/accept/")
    client_for(seller).post(f"/api/exchanges/{swap_id}/complete/")
    assert ExchangeRequest.objects.get(pk=other_id).status == "rejected"


def test_exchanges_are_private_and_filterable(client_for, seller, buyer, make_user, make_listing):
    listing = make_listing(seller)
    exchange_id = _request(client_for(buyer), listing).data["id"]
    outsider = client_for(make_user())
    assert outsider.get(f"/api/exchanges/{exchange_id}/").status_code == 404

    seller_client = client_for(seller)
    selling = seller_client.get("/api/exchanges/", {"role": "seller"}).data
    assert selling["count"] == 1 and selling["results"][0]["role"] == "seller"
    assert seller_client.get("/api/exchanges/", {"role": "requester"}).data["count"] == 0
    assert seller_client.get("/api/exchanges/", {"status": "accepted"}).data["count"] == 0
    assert seller_client.get("/api/exchanges/", {"role": "bogus"}).status_code == 400


def test_cannot_hard_delete_listing_with_history(client_for, seller, buyer, make_listing):
    listing = make_listing(seller)
    exchange_id = _request(client_for(buyer), listing).data["id"]
    assert client_for(seller).delete(f"/api/listings/{listing.id}/").status_code == 204
    listing.refresh_from_db()
    assert listing.status == Listing.Status.WITHDRAWN
    assert ExchangeRequest.objects.get(pk=exchange_id).status == "rejected"


def test_deleting_an_offered_listing_cancels_the_swap(
    client_for, seller, buyer, make_listing, other_book
):
    wanted = make_listing(seller, listing_type="exchange", price=None)
    offered = make_listing(buyer, book=other_book)
    exchange_id = _request(client_for(buyer), wanted, offered_listing=offered.id).data["id"]
    assert client_for(buyer).delete(f"/api/listings/{offered.id}/").status_code == 204
    offered.refresh_from_db()
    assert offered.status == Listing.Status.WITHDRAWN
    exchange = ExchangeRequest.objects.get(pk=exchange_id)
    assert exchange.status == "cancelled" and exchange.offered_listing_id == offered.id


def test_withdrawing_a_listing_rejects_pending_requests(client_for, seller, buyer, make_listing):
    listing = make_listing(seller)
    exchange_id = _request(client_for(buyer), listing).data["id"]
    resp = client_for(seller).patch(f"/api/listings/{listing.id}/", {"status": "withdrawn"})
    assert resp.status_code == 200
    assert ExchangeRequest.objects.get(pk=exchange_id).status == "rejected"


def test_completed_listing_cannot_be_deleted(client_for, seller, make_listing):
    listing = make_listing(seller, status=Listing.Status.COMPLETED)
    assert client_for(seller).delete(f"/api/listings/{listing.id}/").status_code == 400
    listing.refresh_from_db()
    assert listing.status == Listing.Status.COMPLETED

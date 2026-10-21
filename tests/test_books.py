from decimal import Decimal

import pytest

from books.models import Book, Listing
from exchanges.models import ExchangeRequest

pytestmark = pytest.mark.django_db

FAKE_METADATA = {
    "title": "Clean Code",
    "subtitle": "",
    "authors": "Robert C. Martin",
    "publisher": "Prentice Hall",
    "published_year": 2008,
    "page_count": 464,
    "cover_url": "",
    "description": "",
    "isbn_10": "0132350882",
}


@pytest.fixture
def fake_lookup(monkeypatch):
    calls = []

    def fake(isbn13):
        calls.append(isbn13)
        return dict(FAKE_METADATA) if isbn13 == "9780132350884" else None

    monkeypatch.setattr("books.services.fetch_book_metadata", fake)
    return calls


def test_lookup_imports_book_once(client_for, buyer, fake_lookup):
    client = client_for(buyer)
    resp = client.get("/api/books/lookup/", {"isbn": "0-13-235088-2"})
    assert resp.status_code == 200
    assert resp.data["title"] == "Clean Code"
    assert resp.data["isbn_13"] == "9780132350884"

    client.get("/api/books/lookup/", {"isbn": "9780132350884"})
    assert fake_lookup == ["9780132350884"]  # second call served from the DB
    assert Book.objects.count() == 1


def test_lookup_invalid_and_unknown(client_for, buyer, fake_lookup):
    client = client_for(buyer)
    assert client.get("/api/books/lookup/", {"isbn": "123"}).status_code == 400
    assert client.get("/api/books/lookup/", {"isbn": "9780262033848"}).status_code == 404


def test_manual_book_creation_normalises_isbn(client_for, buyer, fake_lookup):
    resp = client_for(buyer).post(
        "/api/books/", {"isbn_13": "0-262-03384-4", "title": "Algorithms"}
    )
    assert resp.status_code == 201
    assert resp.data["isbn_13"] == "9780262033848"
    assert resp.data["isbn_10"] == "0262033844"


def test_manual_book_accepts_hyphenated_isbn13(client_for, buyer, book, fake_lookup):
    client = client_for(buyer)
    resp = client.post("/api/books/", {"isbn_13": "978-0-13-468599-1", "title": "Effective Java"})
    assert resp.status_code == 201, resp.data
    assert resp.data["isbn_13"] == "9780134685991"
    duplicate = client.post("/api/books/", {"isbn_13": "978-0-262-03384-8", "title": "Dup"})
    assert duplicate.status_code == 400


def test_manual_book_uses_catalogue_data_when_known(client_for, buyer, fake_lookup):
    resp = client_for(buyer).post("/api/books/", {"isbn_13": "9780132350884", "title": "Wrong"})
    assert resp.status_code == 201
    assert resp.data["title"] == "Clean Code"


def test_only_staff_can_edit_books(client_for, buyer, book, make_user):
    assert client_for(buyer).patch(f"/api/books/{book.id}/", {"title": "x"}).status_code == 403
    admin = make_user(is_staff=True)
    assert client_for(admin).patch(f"/api/books/{book.id}/", {"title": "x"}).status_code == 200


def test_create_listing_from_isbn_lookup(client_for, seller, fake_lookup):
    client = client_for(seller)
    book_id = client.get("/api/books/lookup/", {"isbn": "9780132350884"}).data["id"]
    resp = client.post(
        "/api/listings/",
        {"book_id": book_id, "condition": "good", "listing_type": "sell", "price": "15.00"},
    )
    assert resp.status_code == 201, resp.data
    assert resp.data["book"]["title"] == "Clean Code"
    assert resp.data["seller"]["id"] == seller.id
    assert resp.data["is_owner"] is True


def test_listing_book_cannot_change(client_for, seller, make_listing, other_book):
    listing = make_listing(seller)
    resp = client_for(seller).patch(f"/api/listings/{listing.id}/", {"book_id": other_book.id})
    assert resp.status_code == 400


def test_isbn10_follows_isbn13_on_edit(book):
    book.isbn_13 = "9780134685991"
    book.save()
    assert book.isbn_10 == "0134685997"


def test_sell_listing_requires_price(client_for, seller, book):
    resp = client_for(seller).post(
        "/api/listings/", {"book_id": book.id, "condition": "good", "listing_type": "sell"}
    )
    assert resp.status_code == 400
    assert "price" in resp.data


def test_donation_clears_price(client_for, seller, book):
    resp = client_for(seller).post(
        "/api/listings/",
        {"book_id": book.id, "condition": "fair", "listing_type": "donate", "price": "9"},
    )
    assert resp.status_code == 201
    assert resp.data["price"] is None


def test_only_seller_can_modify_listing(client_for, seller, buyer, make_listing):
    listing = make_listing(seller)
    url = f"/api/listings/{listing.id}/"
    assert client_for(buyer).patch(url, {"price": "1.00"}).status_code == 403
    assert client_for(buyer).delete(url).status_code == 403
    assert client_for(seller).patch(url, {"price": "20.00"}).status_code == 200


def test_seller_cannot_set_reserved_status(client_for, seller, make_listing):
    listing = make_listing(seller)
    resp = client_for(seller).patch(f"/api/listings/{listing.id}/", {"status": "completed"})
    assert resp.status_code == 400


def test_search_and_filters(client_for, buyer, seller, make_listing, book, other_book):
    make_listing(seller, price=Decimal("10"), condition="new", course_code="CS101")
    make_listing(seller, book=other_book, price=Decimal("40"), condition="poor")
    make_listing(seller, price=Decimal("5"), status=Listing.Status.COMPLETED)
    make_listing(seller, price=Decimal("5"), status=Listing.Status.WITHDRAWN)
    client = client_for(buyer)

    def titles(params):
        resp = client.get("/api/listings/", params)
        assert resp.status_code == 200
        return [r["book"]["title"] for r in resp.data["results"]]

    assert len(titles({})) == 2  # only available ones by default
    assert titles({"search": "algorithms"}) == ["Introduction to Algorithms"]
    assert titles({"isbn": "0-13-468599-7"}) == ["Effective Java"]
    assert titles({"max_price": "20"}) == ["Introduction to Algorithms"]
    assert titles({"condition": ["new", "like_new"]}) == ["Introduction to Algorithms"]
    assert titles({"course_code": "cs101"}) == ["Introduction to Algorithms"]
    assert titles({"ordering": "-price"}) == ["Effective Java", "Introduction to Algorithms"]
    assert len(titles({"status": "completed"})) == 1
    assert len(titles({"status": "withdrawn"})) == 0  # not the buyer's


def test_mine_includes_all_statuses(client_for, seller, make_listing):
    make_listing(seller)
    make_listing(seller, status=Listing.Status.WITHDRAWN)
    resp = client_for(seller).get("/api/listings/mine/")
    assert resp.data["count"] == 2


def test_book_catalog_annotations(client_for, buyer, seller, make_listing, book):
    make_listing(seller, price=Decimal("30"))
    make_listing(seller, price=Decimal("12"))
    resp = client_for(buyer).get(f"/api/books/{book.id}/")
    assert resp.data["available_listings"] == 2
    assert Decimal(resp.data["lowest_price"]) == Decimal("12")


def test_listings_flag_the_viewers_active_request(client_for, seller, buyer, make_listing):
    requested = make_listing(seller)
    declined = make_listing(seller)
    untouched = make_listing(seller)
    ExchangeRequest.objects.create(listing=requested, requester=buyer)
    ExchangeRequest.objects.create(
        listing=declined, requester=buyer, status=ExchangeRequest.Status.REJECTED
    )

    flags = {
        row["id"]: row["has_active_request"]
        for row in client_for(buyer).get("/api/listings/").data["results"]
    }
    assert flags == {requested.id: True, declined.id: False, untouched.id: False}
    # Another student's request is not the seller's.
    seller_view = client_for(seller).get(f"/api/listings/{requested.id}/").data
    assert seller_view["has_active_request"] is False


def listing_details(**changes):
    return {
        "title": "Principles of Management",
        "authors": "Kishor Bahadur Pradhan",
        "edition": "3rd",
        "condition": "good",
        "listing_type": "sell",
        "price": "450",
        **changes,
    }


def test_create_listing_from_book_details(client_for, seller, buyer):
    resp = client_for(seller).post("/api/listings/", listing_details())
    assert resp.status_code == 201, resp.data
    assert resp.data["book"]["title"] == "Principles of Management"
    assert resp.data["book"]["isbn_13"] is None

    # The same book typed differently is the same catalogue entry.
    again = client_for(buyer).post(
        "/api/listings/",
        listing_details(title="  principles of  MANAGEMENT ", authors="kishor bahadur pradhan"),
    )
    assert again.status_code == 201, again.data
    assert again.data["book"]["id"] == resp.data["book"]["id"]
    assert Book.objects.count() == 1


def test_listing_needs_a_book(client_for, seller, book):
    client = client_for(seller)
    missing = client.post("/api/listings/", listing_details(title=""))
    assert missing.status_code == 400
    assert "title" in missing.data

    both = client.post("/api/listings/", listing_details(book_id=book.id))
    assert both.status_code == 400
    assert "book_id" in both.data


def test_seller_can_correct_book_details(client_for, seller):
    client = client_for(seller)
    created = client.post("/api/listings/", listing_details()).data
    resp = client.patch(f"/api/listings/{created['id']}/", {"title": "Principles of Marketing"})
    assert resp.status_code == 200, resp.data
    assert resp.data["book"]["title"] == "Principles of Marketing"
    # Fields left out keep their value.
    assert resp.data["book"]["authors"] == "Kishor Bahadur Pradhan"


def test_book_details_are_locked_while_requested(client_for, seller, buyer):
    client = client_for(seller)
    created = client.post("/api/listings/", listing_details()).data
    ExchangeRequest.objects.create(listing_id=created["id"], requester=buyer)

    changed = client.patch(f"/api/listings/{created['id']}/", {"title": "Something else"})
    assert changed.status_code == 400
    assert "title" in changed.data

    # Saving the form unchanged, e.g. to edit the price, still works.
    unchanged = client.patch(
        f"/api/listings/{created['id']}/",
        {"title": "principles of management", "price": "400"},
    )
    assert unchanged.status_code == 200, unchanged.data
    assert unchanged.data["price"] == "400.00"


def test_book_without_isbn():
    book = Book.objects.create(title="Nepali Grammar")
    assert book.isbn_13 is None
    assert book.isbn_10 == ""
    assert str(book) == "Nepali Grammar"

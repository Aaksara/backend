from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.books.models import Book, Listing
from apps.exchanges.models import MeetupLocation

PASSWORD = "S3cure-pass-phrase"


@pytest.fixture(autouse=True)
def _isolate(settings, monkeypatch):
    settings.UNIVERSITY_EMAIL_DOMAINS = ["university.edu"]
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    cache.clear()  # reset throttling counters

    def no_network(*args, **kwargs):
        raise AssertionError("Tests must not make real HTTP requests")

    monkeypatch.setattr("requests.get", no_network)


@pytest.fixture
def make_user(db):
    counter = {"n": 0}

    def _make(email=None, verified=True, **extra):
        counter["n"] += 1
        email = email or f"student{counter['n']}@university.edu"
        return User.objects.create_user(
            email=email,
            password=PASSWORD,
            full_name=extra.pop("full_name", f"Student {counter['n']}"),
            is_email_verified=verified,
            **extra,
        )

    return _make


@pytest.fixture
def client_for():
    def _client(user=None):
        client = APIClient()
        if user is not None:
            token = RefreshToken.for_user(user).access_token
            client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        return client

    return _client


@pytest.fixture
def seller(make_user):
    return make_user(full_name="Sam Seller")


@pytest.fixture
def buyer(make_user):
    return make_user(full_name="Bea Buyer")


@pytest.fixture
def book(db):
    return Book.objects.create(
        isbn_13="9780262033848", title="Introduction to Algorithms", authors="Cormen, Leiserson"
    )


@pytest.fixture
def other_book(db):
    return Book.objects.create(isbn_13="9780134685991", title="Effective Java", authors="Bloch")


@pytest.fixture
def make_listing(book):
    def _make(seller, **kwargs):
        kwargs.setdefault("book", book)
        kwargs.setdefault("condition", Listing.Condition.GOOD)
        kwargs.setdefault("listing_type", Listing.ListingType.SELL)
        kwargs.setdefault("price", Decimal("25.00"))
        return Listing.objects.create(seller=seller, **kwargs)

    return _make


@pytest.fixture
def location(db):
    return MeetupLocation.objects.create(name="Main Library")


@pytest.fixture
def future_time():
    return (timezone.now() + timedelta(days=1)).isoformat()

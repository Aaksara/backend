"""Fetch book metadata by ISBN from public catalogues (Open Library, then Google Books)."""

import logging

import requests
from django.conf import settings

from .models import Book

logger = logging.getLogger(__name__)

OPEN_LIBRARY_URL = "https://openlibrary.org/api/books"
GOOGLE_BOOKS_URL = "https://www.googleapis.com/books/v1/volumes"


def _year(value) -> int | None:
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    return int(digits[-4:]) if len(digits) >= 4 else None


def _from_open_library(isbn13: str) -> dict | None:
    key = f"ISBN:{isbn13}"
    resp = requests.get(
        OPEN_LIBRARY_URL,
        params={"bibkeys": key, "format": "json", "jscmd": "data"},
        timeout=settings.ISBN_LOOKUP_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json().get(key)
    if not data:
        return None
    cover = data.get("cover") or {}
    return {
        "title": data.get("title", "")[:300],
        "subtitle": data.get("subtitle", "")[:300],
        "authors": ", ".join(a.get("name", "") for a in data.get("authors", []))[:500],
        "publisher": ", ".join(p.get("name", "") for p in data.get("publishers", []))[:255],
        "published_year": _year(data.get("publish_date")),
        "page_count": data.get("number_of_pages"),
        "cover_url": cover.get("large") or cover.get("medium") or "",
        "description": "",
    }


def _from_google_books(isbn13: str) -> dict | None:
    resp = requests.get(
        GOOGLE_BOOKS_URL,
        params={"q": f"isbn:{isbn13}"},
        timeout=settings.ISBN_LOOKUP_TIMEOUT,
    )
    resp.raise_for_status()
    items = resp.json().get("items") or []
    if not items:
        return None
    info = items[0].get("volumeInfo", {})
    images = info.get("imageLinks") or {}
    return {
        "title": info.get("title", "")[:300],
        "subtitle": info.get("subtitle", "")[:300],
        "authors": ", ".join(info.get("authors", []))[:500],
        "publisher": info.get("publisher", "")[:255],
        "published_year": _year(info.get("publishedDate")),
        "page_count": info.get("pageCount"),
        "cover_url": (images.get("thumbnail") or "").replace("http://", "https://"),
        "description": info.get("description", ""),
    }


def fetch_book_metadata(isbn13: str) -> dict | None:
    """Return a dict of Book field values, or None if no catalogue knows the ISBN."""
    for source in (_from_open_library, _from_google_books):
        try:
            metadata = source(isbn13)
        except (requests.RequestException, ValueError) as exc:
            logger.warning("ISBN lookup via %s failed for %s: %s", source.__name__, isbn13, exc)
            continue
        if metadata and metadata.get("title"):
            return metadata
    return None


def get_or_fetch_book(isbn13: str):
    """Return the local Book for an ISBN, importing it from external catalogues if needed."""
    book = Book.objects.filter(isbn_13=isbn13).first()
    if book:
        return book
    metadata = fetch_book_metadata(isbn13)
    if metadata is None:
        return None
    book, _ = Book.objects.get_or_create(isbn_13=isbn13, defaults=metadata)
    return book

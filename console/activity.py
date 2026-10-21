"""A student's history, pieced together from the dates the marketplace already keeps.

There is no audit log, so each event comes from a row's own timestamps: when a listing was
created, when a request was made, answered or completed, and so on. Each event records the
student's side of it, so the console can word it from their point of view.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from itertools import chain

from django.db.models import Q

from exchanges.models import ExchangeRequest

Status = ExchangeRequest.Status


class Kind(StrEnum):
    JOINED = "joined"
    LISTED = "listed"
    REQUESTED = "requested"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    MESSAGED = "messaged"


class Role(StrEnum):
    BUYER = "buyer"
    SELLER = "seller"
    # For events with no other student, like joining.
    NONE = ""


@dataclass(frozen=True)
class Event:
    id: str
    kind: Kind
    at: datetime
    role: Role = Role.NONE
    listing_id: int | None = None
    book_title: str = ""
    counterpart: str = ""


# Each request event: its kind, the date it happened on, and which requests have it.
REQUEST_EVENTS = [
    (Kind.REQUESTED, "created_at", Q()),
    # Only accepting and rejecting set `responded_at`, so a request that has one and was not
    # rejected was accepted, even if it was later cancelled or completed.
    (Kind.ACCEPTED, "responded_at", ~Q(status=Status.REJECTED)),
    (Kind.REJECTED, "responded_at", Q(status=Status.REJECTED)),
    # Nothing changes a cancelled request afterwards, so `updated_at` is when it was cancelled.
    (Kind.CANCELLED, "updated_at", Q(status=Status.CANCELLED)),
    (Kind.COMPLETED, "completed_at", Q()),
]


def _joined(student, limit):
    yield Event(id="joined", kind=Kind.JOINED, at=student.date_joined)


def _listed(student, limit):
    for listing in student.listings.select_related("book").order_by("-created_at")[:limit]:
        yield Event(
            id=f"listing-{listing.pk}",
            kind=Kind.LISTED,
            at=listing.created_at,
            role=Role.SELLER,
            listing_id=listing.pk,
            book_title=listing.book.title,
        )


def _requests(student, limit):
    """Requests the student made (as buyer) and received on their listings (as seller)."""
    sides = [
        (Role.BUYER, Q(requester=student), "listing__seller"),
        (Role.SELLER, Q(listing__seller=student), "requester"),
    ]
    for kind, field, condition in REQUEST_EVENTS:
        for role, side, other in sides:
            requests = (
                ExchangeRequest.objects.filter(side, condition, **{f"{field}__isnull": False})
                .select_related("listing__book", other)
                .order_by(f"-{field}")[:limit]
            )
            for request in requests:
                counterpart = request.listing.seller if role == Role.BUYER else request.requester
                yield Event(
                    id=f"request-{request.pk}-{kind}",
                    kind=kind,
                    at=getattr(request, field),
                    role=role,
                    listing_id=request.listing_id,
                    book_title=request.listing.book.title,
                    counterpart=counterpart.full_name,
                )


def _messaged(student, limit):
    """Conversations opened with or by the student. What they said stays private."""
    sides = [
        (Role.BUYER, student.buyer_conversations, "seller"),
        (Role.SELLER, student.seller_conversations, "buyer"),
    ]
    for role, conversations, other in sides:
        rows = conversations.select_related("listing__book", other).order_by("-created_at")
        for conversation in rows[:limit]:
            yield Event(
                id=f"conversation-{conversation.pk}",
                kind=Kind.MESSAGED,
                at=conversation.created_at,
                role=role,
                listing_id=conversation.listing_id,
                book_title=conversation.listing.book.title,
                counterpart=getattr(conversation, other).full_name,
            )


SOURCES = [_joined, _listed, _requests, _messaged]


def student_activity(student, limit):
    """The student's `limit` newest events, and whether there are older ones.

    Each query fetches at most `limit + 1` rows: enough to fill the page and to tell whether
    anything is left over.
    """
    events = chain.from_iterable(source(student, limit + 1) for source in SOURCES)
    newest = sorted(events, key=lambda event: event.at, reverse=True)
    return newest[:limit], len(newest) > limit

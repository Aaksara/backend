"""State transitions for exchange requests.

Every transition locks the involved listings so two requests can never both
reserve the same book.
"""

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from books.models import Listing

from .models import ExchangeRequest

Status = ExchangeRequest.Status


def _lock(exchange_id):
    exchange = ExchangeRequest.objects.select_for_update().get(pk=exchange_id)
    ids = [exchange.listing_id]
    if exchange.offered_listing_id:
        ids.append(exchange.offered_listing_id)
    locked = {
        listing.pk: listing
        for listing in Listing.objects.select_for_update().filter(pk__in=ids).order_by("pk")
    }
    exchange.listing = locked[exchange.listing_id]
    if exchange.offered_listing_id:
        exchange.offered_listing = locked[exchange.offered_listing_id]
    return exchange


def _require_status(exchange, *allowed):
    if exchange.status not in allowed:
        raise ValidationError(f"Cannot do this while the exchange is '{exchange.status}'.")


def _set_listing_status(listing, status):
    if listing is not None:
        listing.status = status
        listing.save(update_fields=["status", "updated_at"])


@transaction.atomic
def accept(exchange_id, user, meetup_location, meetup_time):
    exchange = _lock(exchange_id)
    if exchange.listing.seller_id != user.id:
        raise PermissionDenied("Only the seller can accept a request.")
    _require_status(exchange, Status.PENDING)
    if exchange.listing.status != Listing.Status.AVAILABLE:
        raise ValidationError("This listing is no longer available.")
    offered = exchange.offered_listing
    if offered is not None and offered.status != Listing.Status.AVAILABLE:
        raise ValidationError("The book offered in exchange is no longer available.")
    if offered is None and exchange.listing.listing_type == Listing.ListingType.EXCHANGE:
        raise ValidationError("The book offered in exchange no longer exists.")

    exchange.status = Status.ACCEPTED
    exchange.meetup_location = meetup_location
    exchange.meetup_time = meetup_time
    exchange.responded_at = timezone.now()
    exchange.save()
    _set_listing_status(exchange.listing, Listing.Status.RESERVED)
    _set_listing_status(offered, Listing.Status.RESERVED)
    return exchange


@transaction.atomic
def reject(exchange_id, user):
    exchange = _lock(exchange_id)
    if exchange.listing.seller_id != user.id:
        raise PermissionDenied("Only the seller can reject a request.")
    _require_status(exchange, Status.PENDING)
    exchange.status = Status.REJECTED
    exchange.responded_at = timezone.now()
    exchange.save()
    return exchange


@transaction.atomic
def cancel(exchange_id, user):
    exchange = _lock(exchange_id)
    is_requester = exchange.requester_id == user.id
    is_seller = exchange.listing.seller_id == user.id
    if not (is_requester or is_seller):
        raise PermissionDenied()
    if is_seller and exchange.status == Status.PENDING:
        raise ValidationError("Reject the request instead of cancelling it.")
    _require_status(exchange, Status.PENDING, Status.ACCEPTED)

    was_accepted = exchange.status == Status.ACCEPTED
    exchange.status = Status.CANCELLED
    exchange.save()
    if was_accepted:
        _set_listing_status(exchange.listing, Listing.Status.AVAILABLE)
        _set_listing_status(exchange.offered_listing, Listing.Status.AVAILABLE)
    return exchange


@transaction.atomic
def complete(exchange_id, user):
    exchange = _lock(exchange_id)
    if user.id not in (exchange.requester_id, exchange.listing.seller_id):
        raise PermissionDenied()
    _require_status(exchange, Status.ACCEPTED)

    exchange.status = Status.COMPLETED
    exchange.completed_at = timezone.now()
    exchange.save()

    traded = [exchange.listing]
    if exchange.offered_listing:
        traded.append(exchange.offered_listing)
    for listing in traded:
        _set_listing_status(listing, Listing.Status.COMPLETED)

    # Other pending requests that ask for, or offer, a traded book can never happen now.
    now = timezone.now()
    ExchangeRequest.objects.filter(
        Q(listing__in=traded) | Q(offered_listing__in=traded), status=Status.PENDING
    ).update(status=Status.REJECTED, responded_at=now, updated_at=now)
    return exchange


def close_pending_requests(listing):
    """A withdrawn listing can no longer be traded, so settle the requests waiting on it."""
    now = timezone.now()
    ExchangeRequest.objects.filter(listing=listing, status=Status.PENDING).update(
        status=Status.REJECTED, responded_at=now, updated_at=now
    )
    ExchangeRequest.objects.filter(offered_listing=listing, status=Status.PENDING).update(
        status=Status.CANCELLED, updated_at=now
    )

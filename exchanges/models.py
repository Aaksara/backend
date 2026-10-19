from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

from utilities.models import TimeStampedModel


class MeetupLocation(models.Model):
    """An approved on-campus spot for handing over books (managed by admins)."""

    name = models.CharField(max_length=120, unique=True)
    description = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class ExchangeRequest(TimeStampedModel):
    """A request from one student for another student's listing.

    Lifecycle: pending -> accepted -> completed, with rejected/cancelled as exits.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"
        COMPLETED = "completed", "Completed"

    ACTIVE_STATUSES = (Status.PENDING, Status.ACCEPTED)

    listing = models.ForeignKey("books.Listing", on_delete=models.CASCADE, related_name="exchanges")
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="exchange_requests"
    )
    offered_price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    offered_listing = models.ForeignKey(
        "books.Listing",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="offered_in_exchanges",
        help_text="For swaps: one of the requester's own listings offered in return.",
    )
    message = models.TextField(blank=True)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    meetup_location = models.ForeignKey(
        MeetupLocation, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    meetup_time = models.DateTimeField(null=True, blank=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["listing", "requester"],
                condition=Q(status__in=["pending", "accepted"]),
                name="one_active_request_per_listing_per_user",
            )
        ]

    def __str__(self):
        return f"{self.requester} -> {self.listing_id} [{self.status}]"

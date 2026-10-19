from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from utilities.models import TimeStampedModel

from .isbn import to_isbn10


class Book(TimeStampedModel):
    """A catalogue entry (an edition), shared by every listing of that ISBN."""

    isbn_13 = models.CharField(max_length=13, unique=True)
    isbn_10 = models.CharField(max_length=10, blank=True)
    title = models.CharField(max_length=300)
    subtitle = models.CharField(max_length=300, blank=True)
    authors = models.CharField(max_length=500, blank=True, help_text="Comma separated")
    publisher = models.CharField(max_length=255, blank=True)
    published_year = models.PositiveSmallIntegerField(null=True, blank=True)
    edition = models.CharField(max_length=50, blank=True)
    page_count = models.PositiveIntegerField(null=True, blank=True)
    cover_url = models.URLField(max_length=500, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["title"]
        indexes = [models.Index(fields=["title"])]

    def __str__(self):
        return f"{self.title} ({self.isbn_13})"

    def save(self, *args, **kwargs):
        self.isbn_10 = to_isbn10(self.isbn_13) or ""
        super().save(*args, **kwargs)


class Listing(TimeStampedModel):
    class Condition(models.TextChoices):
        NEW = "new", "New"
        LIKE_NEW = "like_new", "Like new"
        GOOD = "good", "Good"
        FAIR = "fair", "Fair"
        POOR = "poor", "Poor"

    class ListingType(models.TextChoices):
        SELL = "sell", "Sell"
        EXCHANGE = "exchange", "Exchange"
        DONATE = "donate", "Donate"

    class Status(models.TextChoices):
        AVAILABLE = "available", "Available"
        RESERVED = "reserved", "Reserved"
        COMPLETED = "completed", "Completed"
        WITHDRAWN = "withdrawn", "Withdrawn"

    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="listings"
    )
    book = models.ForeignKey(Book, on_delete=models.PROTECT, related_name="listings")
    condition = models.CharField(max_length=10, choices=Condition.choices)
    listing_type = models.CharField(
        max_length=10, choices=ListingType.choices, default=ListingType.SELL
    )
    price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    description = models.TextField(blank=True)
    course_code = models.CharField(max_length=30, blank=True, db_index=True)
    preferred_location = models.ForeignKey(
        "exchanges.MeetupLocation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="listings",
    )
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.AVAILABLE, db_index=True
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "-created_at"])]

    def __str__(self):
        return f"{self.book.title} by {self.seller} [{self.status}]"


class ListingImage(models.Model):
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="listings/%Y/%m/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["uploaded_at"]

    def __str__(self):
        return f"Image {self.pk} of listing {self.listing_id}"

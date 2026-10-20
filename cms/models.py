from django.core.validators import URLValidator
from django.db import models

from utilities.models import TimeStampedModel


class Slide(TimeStampedModel):
    """A picture in the home page's hero slider. Lower `position` shows first."""

    caption = models.CharField(max_length=150)
    link = models.URLField(
        max_length=500,
        blank=True,
        validators=[URLValidator(schemes=["http", "https"])],
        help_text="Optional page the caption links to.",
    )
    image = models.ImageField(upload_to="slides/%Y/%m/")
    alt_text = models.CharField(
        max_length=200, blank=True, help_text="Describes the image for screen readers."
    )
    is_published = models.BooleanField(default=False)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]

    def __str__(self):
        return self.caption


class HomeSection(models.Model):
    """A section of the storefront home page that the admin can hide or move.

    There is one row per kind. The site header and footer are not sections: they always show.
    """

    class Kind(models.TextChoices):
        HERO = "hero", "Hero"
        HOW_IT_WORKS = "how_it_works", "How it works"
        LISTING_TYPES = "listing_types", "Sell, swap, donate"
        SAFETY = "safety", "Safety"
        CALL_TO_ACTION = "call_to_action", "Call to action"

    kind = models.CharField(max_length=20, choices=Kind.choices, unique=True)
    is_enabled = models.BooleanField(default=True)
    position = models.PositiveIntegerField()

    class Meta:
        ordering = ["position"]

    def __str__(self):
        return self.get_kind_display()

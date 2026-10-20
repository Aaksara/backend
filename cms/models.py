from django.core.validators import URLValidator
from django.db import models

from utilities.models import TimeStampedModel


class Slide(TimeStampedModel):
    """A picture in one of the storefront's sliders. Lower `position` shows first."""

    class Slider(models.TextChoices):
        HOME_HERO = "home_hero", "Home page: top"
        HOME_SAFETY = "home_safety", "Home page: safety"
        SIGN_IN = "sign_in", "Sign-in and sign-up pages"

    slider = models.CharField(max_length=20, choices=Slider.choices, default=Slider.HOME_HERO)
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
        ordering = ["slider", "position", "id"]

    def __str__(self):
        return self.caption

    @classmethod
    def next_position(cls, slider):
        """The position after the last slide in `slider`, so a new or moved slide goes last."""
        last = cls.objects.filter(slider=slider).aggregate(last=models.Max("position"))["last"]
        return 0 if last is None else last + 1


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

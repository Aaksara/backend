from django.conf import settings
from django.core.validators import URLValidator
from django.db import models

from utilities.models import TimeStampedModel


class Banner(TimeStampedModel):
    """An image with a link, shown on the storefront. Lower `position` shows first."""

    class Placement(models.TextChoices):
        HERO = "hero", "Hero carousel"
        PROMOTION = "promotion", "Promotion"
        FOOTER = "footer", "Footer notice"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"

    title = models.CharField(max_length=150)
    target_url = models.URLField(
        max_length=500, validators=[URLValidator(schemes=["http", "https"])]
    )
    image = models.ImageField(
        upload_to="banners/%Y/%m/", width_field="image_width", height_field="image_height"
    )
    image_width = models.PositiveIntegerField(null=True, editable=False)
    image_height = models.PositiveIntegerField(null=True, editable=False)
    alt_text = models.CharField(
        max_length=200, blank=True, help_text="Describes the image for screen readers."
    )
    placement = models.CharField(max_length=10, choices=Placement.choices)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]

    def __str__(self):
        return self.title


class Platform(models.TextChoices):
    WEB = "web", "Website"
    MOBILE = "mobile", "Mobile app"


class PageSection(models.Model):
    """One block of the storefront home page, in the published order."""

    class Kind(models.TextChoices):
        HEADER = "header", "Header and navigation"
        HERO = "hero", "Hero"
        HOW_IT_WORKS = "how_it_works", "How it works"
        LISTING_TYPES = "listing_types", "Sell, swap, donate"
        SAFETY = "safety", "Safety"
        CALL_TO_ACTION = "call_to_action", "Call to action"
        FOOTER = "footer", "Footer"

    class Variant(models.TextChoices):
        LIGHT = "light", "Modern light"
        NAVY = "navy", "Collegiate navy"

    platform = models.CharField(max_length=10, choices=Platform.choices)
    kind = models.CharField(max_length=20, choices=Kind.choices)
    display_title = models.CharField(max_length=120)
    anchor_id = models.SlugField(max_length=60, help_text="In-page anchor, e.g. how-it-works.")
    is_enabled = models.BooleanField(default=True)
    variant = models.CharField(max_length=10, choices=Variant.choices, default=Variant.LIGHT)
    position = models.PositiveIntegerField()

    class Meta:
        ordering = ["platform", "position"]
        constraints = [
            models.UniqueConstraint(
                fields=["platform", "anchor_id"], name="unique_anchor_per_platform"
            )
        ]

    def __str__(self):
        return f"{self.get_platform_display()}: {self.display_title}"


class LayoutRelease(models.Model):
    """A published version of a platform's page sections. The highest version is live."""

    platform = models.CharField(max_length=10, choices=Platform.choices)
    version = models.PositiveIntegerField()
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    published_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["platform", "-version"]
        constraints = [
            models.UniqueConstraint(fields=["platform", "version"], name="unique_layout_version")
        ]

    def __str__(self):
        return f"{self.get_platform_display()} v{self.version}"

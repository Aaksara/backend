from django.db import transaction
from rest_framework.exceptions import ValidationError

from .models import HomeSection, Slide


@transaction.atomic
def reorder_slides(slider, ids):
    """Sets the order of one slider's slides, from a list of all their ids, each once."""
    slides = Slide.objects.select_for_update().filter(slider=slider).in_bulk()
    if len(ids) != len(set(ids)) or set(ids) != set(slides):
        raise ValidationError({"ids": "Send every slide of this slider exactly once."})
    for position, slide_id in enumerate(ids):
        slides[slide_id].position = position
    Slide.objects.bulk_update(slides.values(), ["position"])


@transaction.atomic
def save_home_sections(sections):
    """Saves the order and visibility of every home page section.

    `sections` lists each kind once, top to bottom, as `{"kind", "is_enabled"}`.
    """
    rows = {row.kind: row for row in HomeSection.objects.select_for_update()}
    for position, section in enumerate(sections):
        row = rows.get(section["kind"]) or HomeSection(kind=section["kind"])
        row.position = position
        row.is_enabled = section["is_enabled"]
        row.save()

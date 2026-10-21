"""The text of each home page section that the admin console can edit.

A section's saved content is either empty, meaning the site's built-in text, or complete:
every field below, filled in. Sections with cards or steps always have three of them,
because the page gives each position its own icon and colour.
"""

from rest_framework import serializers

from .models import HomeSection

Kind = HomeSection.Kind

ITEM_COUNT = 3


class SectionContentSerializer(serializers.Serializer):
    # The small line above the title (the badge on the hero).
    eyebrow = serializers.CharField(max_length=60)
    title = serializers.CharField(max_length=120)
    description = serializers.CharField(max_length=300)


class PointSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=60)


class CardSerializer(PointSerializer):
    text = serializers.CharField(max_length=300)


class StepSerializer(CardSerializer):
    note = serializers.CharField(max_length=40)


def _items(serializer):
    return serializer(many=True, min_length=ITEM_COUNT, max_length=ITEM_COUNT)


class SectionWithItemsSerializer(SectionContentSerializer):
    """A section with cards, steps or points. Subclasses say which, as `items`."""

    def validate_items(self, items):
        titles = [item["title"] for item in items]
        if len(set(titles)) != len(titles):
            raise serializers.ValidationError("Give each one a different title.")
        return items


class HeroContentSerializer(SectionWithItemsSerializer):
    # The short assurances under the buttons.
    items = _items(PointSerializer)


class HowItWorksContentSerializer(SectionWithItemsSerializer):
    items = _items(StepSerializer)


class CardsContentSerializer(SectionWithItemsSerializer):
    items = _items(CardSerializer)


CONTENT_SERIALIZERS = {
    Kind.HERO: HeroContentSerializer,
    Kind.HOW_IT_WORKS: HowItWorksContentSerializer,
    Kind.LISTING_TYPES: CardsContentSerializer,
    Kind.SAFETY: CardsContentSerializer,
    Kind.CALL_TO_ACTION: SectionContentSerializer,
}

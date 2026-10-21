from pathlib import Path

from django.core.files import File
from django.db import transaction

from .models import Slide

IMAGES = Path(__file__).resolve().parent / "seed_slides"

# The slides the storefront shows when a slider has none: (image, caption, description).
DEFAULT_SLIDES = {
    Slide.Slider.HOME_HERO: [
        (
            "hero-find.svg",
            "Find the books for your course",
            "A phone searching for a course code, with matching textbooks, between library shelves",
        ),
        (
            "hero-list.svg",
            "List a book in a minute",
            "A phone showing a textbook's ISBN barcode beside a priced stack of books",
        ),
        (
            "hero-pass-on.svg",
            "Pass your textbooks on",
            "One student handing a textbook to another under a graduation cap",
        ),
    ],
    Slide.Slider.HOME_SAFETY: [
        (
            "safety-inspect.svg",
            "Check the book before you pay",
            "A magnifying glass over an open textbook next to a condition checklist",
        ),
        (
            "safety-meetup.svg",
            "Meet at approved campus spots",
            "Two students meeting outside a campus library marked with a map pin",
        ),
        (
            "safety-verified.svg",
            "Trade only with students from your university",
            "A student ID card with a university email beside a verified shield",
        ),
    ],
    Slide.Slider.SIGN_IN: [
        (
            "campus-library.webp",
            "Find the books for your course",
            "Curved library shelves full of books",
        ),
        ("textbook-stack.webp", "List a book in seconds", "A stack of textbooks"),
        ("graduation.webp", "Pass your textbooks on", "Graduates throwing their caps in the air"),
    ],
}


def add_default_slides(slider):
    """Gives an empty slider the storefront's built-in slides, published, so the admin can edit
    them. Returns how many were added: none when the slider already has slides."""
    if Slide.objects.filter(slider=slider).exists():
        return 0
    slides = DEFAULT_SLIDES[slider]
    with transaction.atomic():
        for position, (image, caption, alt_text) in enumerate(slides):
            with (IMAGES / image).open("rb") as file:
                Slide.objects.create(
                    slider=slider,
                    caption=caption,
                    alt_text=alt_text,
                    image=File(file, name=image),
                    is_published=True,
                    position=position,
                )
    return len(slides)

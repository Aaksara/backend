from django.core.management.base import BaseCommand

from cms.defaults import add_default_slides
from cms.models import Slide


class Command(BaseCommand):
    help = "Give every slider that has no slides the storefront's built-in ones (idempotent)."

    def handle(self, *args, **options):
        for slider in Slide.Slider:
            added = add_default_slides(slider)
            if added:
                self.stdout.write(self.style.SUCCESS(f"{slider.label}: {added} slides added."))
            else:
                self.stdout.write(f"{slider.label}: has slides already, left as it is.")

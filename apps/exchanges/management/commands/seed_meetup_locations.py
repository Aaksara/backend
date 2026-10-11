from django.core.management.base import BaseCommand

from apps.exchanges.models import MeetupLocation

DEFAULT_LOCATIONS = [
    ("Main Library Entrance", "Ground floor, by the information desk"),
    ("Student Union Cafeteria", "Near the main seating area"),
    ("Science Block Lobby", "Opposite the lifts"),
    ("Campus Bookstore", "Outside the front doors"),
]


class Command(BaseCommand):
    help = "Create a default set of on-campus meetup locations (idempotent)."

    def handle(self, *args, **options):
        created = 0
        for name, description in DEFAULT_LOCATIONS:
            _, was_created = MeetupLocation.objects.get_or_create(
                name=name, defaults={"description": description}
            )
            created += was_created
        self.stdout.write(self.style.SUCCESS(f"{created} meetup location(s) created."))

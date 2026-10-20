from django.contrib.auth.management.commands import createsuperuser
from django.core.management.base import CommandError


class Command(createsuperuser.Command):
    """Django's createsuperuser, reporting "a super admin already exists" without a traceback."""

    def handle(self, *args, **options):
        try:
            return super().handle(*args, **options)
        except ValueError as exc:
            raise CommandError(str(exc)) from None

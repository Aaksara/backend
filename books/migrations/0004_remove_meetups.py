from django.db import migrations


class Migration(migrations.Migration):
    """Listings no longer have a preferred meetup spot.

    Only Django's model state changes: the database column stays, unused and nullable, so
    the code still running during a release keeps working. A later release drops it, as the
    README's release notes require.
    """

    dependencies = [("books", "0003_isbn_optional")]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveField(model_name="listing", name="preferred_location"),
            ],
        ),
    ]

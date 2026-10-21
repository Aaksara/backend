from django.db import migrations


class Migration(migrations.Migration):
    """Exchanges no longer have a meetup spot and time, and meetup locations are gone.

    Only Django's model state changes: the columns and table stay, unused and nullable, so
    the code still running during a release keeps working. A later release drops them, as
    the README's release notes require.
    """

    dependencies = [
        ("books", "0004_remove_meetups"),
        ("exchanges", "0001_initial"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveField(model_name="exchangerequest", name="meetup_location"),
                migrations.RemoveField(model_name="exchangerequest", name="meetup_time"),
                migrations.DeleteModel(name="MeetupLocation"),
            ],
        ),
    ]

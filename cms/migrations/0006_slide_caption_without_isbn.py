from django.db import migrations

OLD_CAPTION = "List a book by its ISBN"
NEW_CAPTION = "List a book in a minute"


def forwards(apps, schema_editor):
    """Listing no longer starts from the ISBN. Only the untouched built-in caption changes."""
    Slide = apps.get_model("cms", "Slide")
    Slide.objects.filter(slider="home_hero", caption=OLD_CAPTION).update(caption=NEW_CAPTION)


def backwards(apps, schema_editor):
    Slide = apps.get_model("cms", "Slide")
    Slide.objects.filter(slider="home_hero", caption=NEW_CAPTION).update(caption=OLD_CAPTION)


class Migration(migrations.Migration):
    dependencies = [("cms", "0005_homesection_content")]

    operations = [migrations.RunPython(forwards, backwards)]

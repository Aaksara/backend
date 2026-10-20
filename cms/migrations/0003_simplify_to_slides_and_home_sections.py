import django.core.validators
from django.db import migrations, models

HOME_SECTION_KINDS = ["hero", "how_it_works", "listing_types", "safety", "call_to_action"]


def convert_content(apps, schema_editor):
    """Keeps existing banners as slides and keeps one ordered row per home section."""
    Slide = apps.get_model("cms", "Slide")
    Slide.objects.filter(status="published").update(is_published=True)

    HomeSection = apps.get_model("cms", "HomeSection")
    # The website's first section of each kind wins; mobile, header and footer rows go.
    kept = {}
    web = HomeSection.objects.filter(platform="web", kind__in=HOME_SECTION_KINDS)
    for section in web.order_by("position"):
        kept.setdefault(section.kind, section)
    HomeSection.objects.exclude(pk__in=[section.pk for section in kept.values()]).delete()

    ordered = [*kept, *(kind for kind in HOME_SECTION_KINDS if kind not in kept)]
    for position, kind in enumerate(ordered):
        # The old columns are still required at this point, so a new row fills them in.
        section = kept.get(kind) or HomeSection(
            kind=kind, platform="web", display_title=kind, anchor_id=kind.replace("_", "-")
        )
        section.position = position
        section.save()


def clear_content(apps, schema_editor):
    """When migrating back: the old columns cannot be refilled, so start the old tables empty."""
    apps.get_model("cms", "Slide").objects.all().delete()
    apps.get_model("cms", "HomeSection").objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [("cms", "0002_seed_home_layout")]

    operations = [
        # Banners become hero slides.
        migrations.RenameModel("Banner", "Slide"),
        migrations.RenameField("slide", "title", "caption"),
        migrations.RenameField("slide", "target_url", "link"),
        migrations.AddField("slide", "is_published", models.BooleanField(default=False)),
        # Page sections become the home page's sections, without versions or styling.
        migrations.RenameModel("PageSection", "HomeSection"),
        migrations.RemoveConstraint("homesection", "unique_anchor_per_platform"),
        migrations.RunPython(convert_content, migrations.RunPython.noop),
        migrations.RemoveField("slide", "status"),
        migrations.RemoveField("slide", "placement"),
        migrations.RemoveField("slide", "image_width"),
        migrations.RemoveField("slide", "image_height"),
        migrations.AlterField(
            "slide",
            "link",
            models.URLField(
                blank=True,
                help_text="Optional page the caption links to.",
                max_length=500,
                validators=[django.core.validators.URLValidator(schemes=["http", "https"])],
            ),
        ),
        migrations.AlterField("slide", "image", models.ImageField(upload_to="slides/%Y/%m/")),
        migrations.RemoveField("homesection", "platform"),
        migrations.RemoveField("homesection", "display_title"),
        migrations.RemoveField("homesection", "anchor_id"),
        migrations.RemoveField("homesection", "variant"),
        migrations.AlterField(
            "homesection",
            "kind",
            models.CharField(
                choices=[
                    ("hero", "Hero"),
                    ("how_it_works", "How it works"),
                    ("listing_types", "Sell, swap, donate"),
                    ("safety", "Safety"),
                    ("call_to_action", "Call to action"),
                ],
                max_length=20,
                unique=True,
            ),
        ),
        migrations.AlterModelOptions("homesection", {"ordering": ["position"]}),
        migrations.DeleteModel("LayoutRelease"),
        # Runs first when migrating back; see clear_content.
        migrations.RunPython(migrations.RunPython.noop, clear_content),
    ]

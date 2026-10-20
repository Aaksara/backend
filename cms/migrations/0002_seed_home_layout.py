from django.db import migrations

# The storefront home page as built today, top to bottom, so the admin console starts from
# what students actually see.
HOME_SECTIONS = [
    ("header", "Site header", "site-header", "light"),
    ("hero", "Buy, swap and donate textbooks on campus", "hero", "light"),
    ("how_it_works", "How Akshara works", "how-it-works", "light"),
    ("listing_types", "Sell, swap or donate", "sell-swap-donate", "light"),
    ("safety", "Trade only with students from your university.", "safety", "light"),
    ("call_to_action", "Got books from last semester?", "get-started", "navy"),
    ("footer", "Site footer", "site-footer", "navy"),
]


def seed(apps, schema_editor):
    PageSection = apps.get_model("cms", "PageSection")
    LayoutRelease = apps.get_model("cms", "LayoutRelease")
    for platform in ("web", "mobile"):
        PageSection.objects.bulk_create(
            PageSection(
                platform=platform,
                kind=kind,
                display_title=title,
                anchor_id=anchor,
                variant=variant,
                position=position,
            )
            for position, (kind, title, anchor, variant) in enumerate(HOME_SECTIONS)
        )
        LayoutRelease.objects.create(platform=platform, version=1)


def unseed(apps, schema_editor):
    apps.get_model("cms", "PageSection").objects.all().delete()
    apps.get_model("cms", "LayoutRelease").objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [("cms", "0001_initial")]

    operations = [migrations.RunPython(seed, unseed)]

from django.db import migrations

# Built-in text that promised admin-approved meetup spots, and what replaces it. Only text
# still exactly as shipped changes; anything an admin rewrote is left alone.
REPLACEMENTS = {
    "Meet at approved campus spots": "Hand books over in person",
    (
        "Pass on the books from last semester and find the ones you need for the next. "
        "Meet a fellow student at an approved spot on campus to hand them over."
    ): (
        "Pass on the books from last semester and find the ones you need for the next. "
        "Meet a fellow student on campus to hand them over."
    ),
    (
        "Hand the book over at an approved spot on campus, at a time you both agree on. "
        "Check its condition before you pay."
    ): (
        "Agree with the other student where and when to meet on campus. "
        "Check the book's condition before you pay."
    ),
    "Approved meeting spots": "Meet in person",
    (
        "Handovers take place at campus locations approved by the Akshara team, "
        "at a time you both agree on."
    ): "Pick a busy, public place on campus and a time that suits you both.",
}


def _replace(value, replacements):
    if isinstance(value, str):
        return replacements.get(value, value)
    if isinstance(value, list):
        return [_replace(item, replacements) for item in value]
    if isinstance(value, dict):
        return {key: _replace(item, replacements) for key, item in value.items()}
    return value


def _apply(apps, replacements):
    Slide = apps.get_model("cms", "Slide")
    for old, new in replacements.items():
        Slide.objects.filter(caption=old).update(caption=new)

    HomeSection = apps.get_model("cms", "HomeSection")
    for section in HomeSection.objects.exclude(content={}):
        content = _replace(section.content, replacements)
        if content != section.content:
            section.content = content
            section.save(update_fields=["content"])


def forwards(apps, schema_editor):
    _apply(apps, REPLACEMENTS)


def backwards(apps, schema_editor):
    _apply(apps, {new: old for old, new in REPLACEMENTS.items()})


class Migration(migrations.Migration):
    dependencies = [("cms", "0006_slide_caption_without_isbn")]

    operations = [migrations.RunPython(forwards, backwards)]

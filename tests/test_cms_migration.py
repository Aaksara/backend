import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

BEFORE = [("cms", "0002_seed_home_layout")]
AFTER = [("cms", "0003_simplify_to_slides_and_home_sections")]


def migrate(targets):
    executor = MigrationExecutor(connection)
    executor.migrate(targets)
    executor.loader.build_graph()
    return executor.loader.project_state(targets).apps


@pytest.mark.django_db(transaction=True)
def test_existing_banners_and_section_order_survive_the_simplification():
    old = migrate(BEFORE)
    # With the size given, the old model does not open the (missing) image file.
    size = {"image_width": 1, "image_height": 1}
    old.get_model("cms", "Banner").objects.create(
        title="Live",
        target_url="https://akshara.app/",
        image="banners/a.png",
        placement="promotion",
        status="published",
        **size,
    )
    old.get_model("cms", "Banner").objects.create(
        title="Draft",
        target_url="https://akshara.app/",
        image="banners/b.png",
        placement="hero",
        **size,
    )
    sections = old.get_model("cms", "PageSection").objects
    for position, kind in enumerate(["header", "safety", "hero", "safety", "footer"]):
        sections.create(
            platform="web",
            kind=kind,
            display_title=kind,
            anchor_id=f"{kind}-{position}",
            position=position,
            is_enabled=kind != "safety" or position == 1,
        )
    sections.create(platform="mobile", kind="hero", display_title="m", anchor_id="m", position=0)

    try:
        new = migrate(AFTER)
        slides = new.get_model("cms", "Slide").objects.order_by("caption")
        home = new.get_model("cms", "HomeSection").objects.order_by("position")

        assert [(s.caption, s.is_published) for s in slides] == [("Draft", False), ("Live", True)]
        # Kept web sections first, in their order; missing kinds appended, visible.
        assert [s.kind for s in home] == [
            "safety",
            "hero",
            "how_it_works",
            "listing_types",
            "call_to_action",
        ]
        assert all(s.is_enabled for s in home)
    finally:
        migrate(MigrationExecutor(connection).loader.graph.leaf_nodes())

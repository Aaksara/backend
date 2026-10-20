from django.db import transaction
from rest_framework.exceptions import APIException, ValidationError

from .models import Banner, LayoutRelease, PageSection


class LayoutConflict(APIException):
    status_code = 409
    default_code = "layout_conflict"


def live_release(platform):
    """The platform's latest release, or None before the first publish."""
    return LayoutRelease.objects.filter(platform=platform).select_related("published_by").first()


@transaction.atomic
def publish_layout(platform, sections, base_version, user):
    """Replaces the platform's sections and records a new release.

    `base_version` is the version the editor started from. If someone published since,
    the request is refused rather than silently overwriting their work.
    """
    # Lock the platform's releases so two publishes cannot both pass the version check.
    current = (
        LayoutRelease.objects.select_for_update()
        .filter(platform=platform)
        .order_by("-version")
        .first()
    )
    current_version = current.version if current else 0
    if base_version != current_version:
        raise LayoutConflict(
            f"Version {current_version} was published after you started editing. "
            "Reload to see it, then make your changes again."
        )

    PageSection.objects.filter(platform=platform).delete()
    PageSection.objects.bulk_create(
        PageSection(platform=platform, position=index, **section)
        for index, section in enumerate(sections)
    )
    return LayoutRelease.objects.create(
        platform=platform, version=current_version + 1, published_by=user
    )


@transaction.atomic
def reorder_banners(ids):
    """Sets display order from a list containing every banner id exactly once."""
    banners = Banner.objects.select_for_update().in_bulk()
    if len(ids) != len(set(ids)) or set(ids) != set(banners):
        raise ValidationError({"ids": "Send every banner id exactly once."})
    for position, banner_id in enumerate(ids):
        banners[banner_id].position = position
    Banner.objects.bulk_update(banners.values(), ["position"])

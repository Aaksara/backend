import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import CommandError, call_command
from PIL import Image

from accounts.models import User
from books.models import Listing
from cms.models import Banner, LayoutRelease, PageSection
from exchanges.models import MeetupLocation

pytestmark = pytest.mark.django_db


@pytest.fixture
def super_admin(db):
    return User.objects.create_superuser(
        email="admin@akshara.app", password="An-admin-pass-123", full_name="Ada Admin"
    )


@pytest.fixture
def admin_client(client_for, super_admin):
    return client_for(super_admin)


@pytest.fixture(autouse=True)
def _media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


def png(name="banner.png", size=(1280, 480)):
    buffer = io.BytesIO()
    Image.new("RGB", size, "navy").save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


def make_banner(**fields):
    fields.setdefault("title", "Spring drive")
    fields.setdefault("target_url", "https://akshara.app/spring")
    fields.setdefault("placement", Banner.Placement.HERO)
    fields.setdefault("image", png())
    return Banner.objects.create(**fields)


# --- The super admin ----------------------------------------------------------------------


def test_only_one_super_admin_can_exist(super_admin):
    with pytest.raises(ValueError, match="already exists"):
        User.objects.create_superuser(email="second@akshara.app", password="x", full_name="Two")


def test_createsuperuser_command_refuses_a_second_admin_cleanly(super_admin, monkeypatch):
    monkeypatch.setenv("DJANGO_SUPERUSER_PASSWORD", "Another-pass-123")
    with pytest.raises(CommandError, match="already exists"):
        call_command("createsuperuser", interactive=False, email="two@akshara.app", full_name="Two")


def test_me_tells_the_console_who_is_super_admin(admin_client, client_for, make_user):
    assert admin_client.get("/api/auth/me/").data["is_superuser"] is True
    assert client_for(make_user()).get("/api/auth/me/").data["is_superuser"] is False


@pytest.mark.parametrize(
    "url",
    [
        "/api/admin/students/",
        "/api/admin/students/summary/",
        "/api/admin/banners/",
        "/api/admin/layouts/web/",
        "/api/admin/meetup-locations/",
        "/api/admin/campus/",
    ],
)
def test_admin_api_refuses_everyone_else(client_for, make_user, url):
    assert client_for().get(url).status_code == 401
    assert client_for(make_user()).get(url).status_code == 403


# --- Students -----------------------------------------------------------------------------


def test_student_list_counts_activity_and_leaves_out_staff(
    admin_client, seller, buyer, make_listing
):
    make_listing(seller)
    make_listing(seller, status=Listing.Status.COMPLETED)

    resp = admin_client.get("/api/admin/students/", {"ordering": "full_name"})

    assert resp.status_code == 200
    rows = {row["email"]: row for row in resp.data["results"]}
    assert set(rows) == {seller.email, buyer.email}
    assert rows[seller.email]["listing_count"] == 2
    assert rows[seller.email]["active_listing_count"] == 1


def test_student_filters_and_search(admin_client, make_user):
    make_user(full_name="Maya Lin")
    make_user(full_name="Dan Kim", verified=False)

    unverified = admin_client.get("/api/admin/students/", {"is_email_verified": "false"})
    found = admin_client.get("/api/admin/students/", {"search": "maya"})

    assert [row["full_name"] for row in unverified.data["results"]] == ["Dan Kim"]
    assert [row["full_name"] for row in found.data["results"]] == ["Maya Lin"]


def test_student_detail_includes_recent_listings(admin_client, seller, make_listing):
    make_listing(seller, course_code="CS 61A")

    resp = admin_client.get(f"/api/admin/students/{seller.pk}/")

    assert resp.data["recent_listings"][0]["course_code"] == "CS 61A"
    assert resp.data["recent_listings"][0]["title"] == "Introduction to Algorithms"


def test_summary_counts(admin_client, seller, buyer, make_listing, make_user):
    make_listing(seller)
    make_user(verified=False, is_active=False)

    data = admin_client.get("/api/admin/students/summary/").data

    assert data["students"] == 3
    assert data["verified"] == 2
    assert data["suspended"] == 1
    assert data["active_sellers"] == 1


def test_suspend_signs_the_student_out_and_reactivate_restores(admin_client, client_for, buyer):
    login = client_for().post(
        "/api/auth/login/", {"email": buyer.email, "password": "S3cure-pass-phrase"}
    )

    suspended = admin_client.post(f"/api/admin/students/{buyer.pk}/suspend/")
    refresh = client_for().post("/api/auth/token/refresh/", {"refresh": login.data["refresh"]})
    reactivated = admin_client.post(f"/api/admin/students/{buyer.pk}/reactivate/")

    assert suspended.data["is_active"] is False
    assert refresh.status_code == 401
    assert reactivated.data["is_active"] is True


def test_verify_and_resend_verification(admin_client, make_user, mailoutbox):
    student = make_user(verified=False)

    sent = admin_client.post(f"/api/admin/students/{student.pk}/resend-verification/")
    verified = admin_client.post(f"/api/admin/students/{student.pk}/verify-email/")
    again = admin_client.post(f"/api/admin/students/{student.pk}/resend-verification/")

    assert sent.status_code == 200
    assert len(mailoutbox) == 1
    assert verified.data["is_email_verified"] is True
    assert again.status_code == 400


def test_export_is_csv_of_the_filtered_list_and_defuses_formulas(admin_client, make_user):
    make_user(full_name="=HYPERLINK(1)")
    make_user(full_name="Hidden", verified=False)

    resp = admin_client.get("/api/admin/students/export/", {"is_email_verified": "true"})
    lines = resp.content.decode().splitlines()

    assert resp["Content-Type"].startswith("text/csv")
    assert lines[0].startswith("Name,Email")
    assert len(lines) == 2
    assert lines[1].startswith("'=HYPERLINK(1)")


# --- Banners ------------------------------------------------------------------------------


def test_create_banner_with_image(admin_client):
    resp = admin_client.post(
        "/api/admin/banners/",
        {
            "title": "Donate drive",
            "target_url": "https://akshara.app/donate",
            "placement": "hero",
            "image": png(),
        },
        format="multipart",
    )

    assert resp.status_code == 201
    assert (resp.data["image_width"], resp.data["image_height"]) == (1280, 480)
    assert resp.data["status"] == "draft"


def test_banner_rejects_non_web_links(admin_client):
    resp = admin_client.post(
        "/api/admin/banners/",
        {"title": "x", "target_url": "javascript:alert(1)", "placement": "hero", "image": png()},
        format="multipart",
    )
    assert resp.status_code == 400
    assert "target_url" in resp.data


def test_update_without_new_image_keeps_it(admin_client):
    banner = make_banner()

    resp = admin_client.patch(
        f"/api/admin/banners/{banner.pk}/", {"status": "published"}, format="multipart"
    )

    banner.refresh_from_db()
    assert resp.status_code == 200
    assert banner.status == "published"
    assert banner.image.storage.exists(banner.image.name)


def test_new_banners_go_last_even_after_deletes(admin_client):
    first, _ = make_banner(title="A", position=0), make_banner(title="B", position=1)
    admin_client.delete(f"/api/admin/banners/{first.pk}/")

    created = admin_client.post(
        "/api/admin/banners/",
        {"title": "C", "target_url": "https://akshara.app/c", "placement": "hero", "image": png()},
        format="multipart",
    )

    assert [row["title"] for row in admin_client.get("/api/admin/banners/").data] == ["B", "C"]
    assert created.data["position"] == 2


def test_reorder_needs_every_banner_once(admin_client):
    first, second = make_banner(title="A"), make_banner(title="B")

    partial = admin_client.post("/api/admin/banners/reorder/", {"ids": [first.pk]}, format="json")
    resp = admin_client.post(
        "/api/admin/banners/reorder/", {"ids": [second.pk, first.pk]}, format="json"
    )

    assert partial.status_code == 400
    assert [row["title"] for row in resp.data] == ["B", "A"]


def test_public_banners_show_only_published(client_for):
    make_banner(title="Live", status=Banner.Status.PUBLISHED)
    make_banner(title="Draft")

    resp = client_for().get("/api/cms/banners/", {"placement": "hero"})

    assert [row["title"] for row in resp.data] == ["Live"]


# --- Page layouts -------------------------------------------------------------------------


def sections_payload(platform="web"):
    return [
        {
            "kind": section.kind,
            "display_title": section.display_title,
            "anchor_id": section.anchor_id,
            "is_enabled": section.is_enabled,
            "variant": section.variant,
        }
        for section in PageSection.objects.filter(platform=platform)
    ]


def test_layout_starts_from_the_seeded_home_page(admin_client):
    resp = admin_client.get("/api/admin/layouts/web/")

    assert resp.data["version"] == 1
    assert resp.data["sections"][0]["kind"] == "header"


def test_publish_reorders_and_bumps_the_version(admin_client, super_admin):
    sections = sections_payload()
    sections.reverse()

    resp = admin_client.put(
        "/api/admin/layouts/web/", {"base_version": 1, "sections": sections}, format="json"
    )

    assert resp.status_code == 200
    assert resp.data["version"] == 2
    assert resp.data["published_by"] == "Ada Admin"
    assert resp.data["sections"][0]["kind"] == "footer"
    assert LayoutRelease.objects.filter(platform="mobile").get().version == 1


def test_publish_refuses_a_stale_draft(admin_client):
    body = {"base_version": 1, "sections": sections_payload()}
    admin_client.put("/api/admin/layouts/web/", body, format="json")

    stale = admin_client.put("/api/admin/layouts/web/", body, format="json")

    assert stale.status_code == 409


def test_publish_refuses_repeated_anchors(admin_client):
    sections = sections_payload()
    sections[1]["anchor_id"] = sections[0]["anchor_id"]

    resp = admin_client.put(
        "/api/admin/layouts/web/", {"base_version": 1, "sections": sections}, format="json"
    )

    assert resp.status_code == 400
    assert "sections" in resp.data


def test_unknown_platform_is_not_found(admin_client, client_for):
    assert admin_client.get("/api/admin/layouts/tv/").status_code == 404
    assert client_for().get("/api/cms/layouts/tv/").status_code == 404


def test_public_layout_hides_disabled_sections(client_for):
    PageSection.objects.filter(platform="web", kind="safety").update(is_enabled=False)

    kinds = [row["kind"] for row in client_for().get("/api/cms/layouts/web/").data]

    assert "safety" not in kinds
    assert kinds[0] == "header"


# --- Campus -------------------------------------------------------------------------------


def test_meetup_locations_include_retired_ones_and_cannot_be_deleted(admin_client, location):
    retired = MeetupLocation.objects.create(name="Old gym", is_active=False)

    listed = admin_client.get("/api/admin/meetup-locations/")
    renamed = admin_client.patch(
        f"/api/admin/meetup-locations/{retired.pk}/", {"is_active": True}, format="json"
    )
    deleted = admin_client.delete(f"/api/admin/meetup-locations/{location.pk}/")

    assert {row["name"] for row in listed.data} == {"Main Library", "Old gym"}
    assert renamed.data["is_active"] is True
    assert deleted.status_code == 405


def test_campus_settings_show_email_domains(admin_client):
    assert admin_client.get("/api/admin/campus/").data == {"email_domains": ["university.edu"]}

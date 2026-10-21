import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import CommandError, call_command
from PIL import Image

from accounts.models import User
from books.models import Listing
from cms.content import CONTENT_SERIALIZERS
from cms.models import HomeSection, Slide
from exchanges import services
from exchanges.models import ExchangeRequest, MeetupLocation

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


def png(name="slide.png", size=(1280, 480)):
    buffer = io.BytesIO()
    Image.new("RGB", size, "navy").save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


def make_slide(**fields):
    fields.setdefault("caption", "Spring drive")
    fields.setdefault("image", png())
    return Slide.objects.create(**fields)


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
        "/api/admin/slides/",
        "/api/admin/home-sections/",
        "/api/admin/home-sections/hero/content/",
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


def test_unverify_signs_the_student_out(admin_client, client_for, buyer):
    login = client_for().post(
        "/api/auth/login/", {"email": buyer.email, "password": "S3cure-pass-phrase"}
    )

    unverified = admin_client.post(f"/api/admin/students/{buyer.pk}/unverify-email/")
    refresh = client_for().post("/api/auth/token/refresh/", {"refresh": login.data["refresh"]})

    assert unverified.data["is_email_verified"] is False
    assert refresh.status_code == 401


def test_student_listings_are_all_of_theirs_with_request_counts(
    admin_client, seller, buyer, make_listing
):
    wanted = make_listing(seller)
    make_listing(seller, status=Listing.Status.WITHDRAWN)
    make_listing(buyer)
    ExchangeRequest.objects.create(listing=wanted, requester=buyer)

    every = admin_client.get(f"/api/admin/students/{seller.pk}/listings/")
    withdrawn = admin_client.get(
        f"/api/admin/students/{seller.pk}/listings/", {"status": "withdrawn"}
    )
    unknown = admin_client.get(f"/api/admin/students/{seller.pk}/listings/", {"status": "gone"})

    assert every.data["count"] == 2
    assert {row["id"]: row["request_count"] for row in every.data["results"]}[wanted.pk] == 1
    assert [row["status"] for row in withdrawn.data["results"]] == ["withdrawn"]
    assert unknown.status_code == 400


def test_activity_tells_each_side_of_an_exchange(admin_client, seller, buyer, make_listing):
    listing = make_listing(seller)
    request = ExchangeRequest.objects.create(listing=listing, requester=buyer)
    services.accept(request.pk, seller, meetup_location=None, meetup_time=None)
    services.complete(request.pk, buyer)

    def kinds(student):
        events = admin_client.get(f"/api/admin/students/{student.pk}/activity/").data["results"]
        return [(event["kind"], event["role"]) for event in events]

    assert kinds(seller) == [
        ("completed", "seller"),
        ("accepted", "seller"),
        ("requested", "seller"),
        ("listed", "seller"),
        ("joined", ""),
    ]
    assert kinds(buyer)[:3] == [
        ("completed", "buyer"),
        ("accepted", "buyer"),
        ("requested", "buyer"),
    ]


def test_activity_pages_with_a_limit(admin_client, seller, make_listing):
    for _ in range(3):
        make_listing(seller)

    first = admin_client.get(f"/api/admin/students/{seller.pk}/activity/", {"limit": 2}).data
    whole = admin_client.get(f"/api/admin/students/{seller.pk}/activity/", {"limit": 10}).data

    assert len(first["results"]) == 2
    assert first["has_more"] is True
    assert len(whole["results"]) == 4
    assert whole["has_more"] is False


def test_activity_limit_must_be_in_range(admin_client, seller):
    url = f"/api/admin/students/{seller.pk}/activity/"

    assert admin_client.get(url, {"limit": "many"}).status_code == 400
    assert admin_client.get(url, {"limit": 501}).status_code == 400


def test_export_is_csv_of_the_filtered_list_and_defuses_formulas(admin_client, make_user):
    make_user(full_name="=HYPERLINK(1)")
    make_user(full_name="Hidden", verified=False)

    resp = admin_client.get("/api/admin/students/export/", {"is_email_verified": "true"})
    lines = resp.content.decode().splitlines()

    assert resp["Content-Type"].startswith("text/csv")
    assert lines[0].startswith("Name,Email")
    assert len(lines) == 2
    assert lines[1].startswith("'=HYPERLINK(1)")


# --- Slides -------------------------------------------------------------------------------


def test_create_slide_with_image(admin_client):
    resp = admin_client.post(
        "/api/admin/slides/",
        {
            "slider": "home_hero",
            "caption": "Donate drive",
            "link": "https://akshara.app/donate",
            "image": png(),
        },
        format="multipart",
    )

    assert resp.status_code == 201
    assert resp.data["is_published"] is False
    assert resp.data["image"].endswith(".png")


def test_new_slide_must_say_which_slider(admin_client):
    resp = admin_client.post(
        "/api/admin/slides/", {"caption": "x", "image": png()}, format="multipart"
    )
    assert resp.status_code == 400
    assert "slider" in resp.data


def test_slide_link_is_optional_but_must_be_a_web_address(admin_client):
    without = admin_client.post(
        "/api/admin/slides/",
        {"slider": "sign_in", "caption": "x", "image": png()},
        format="multipart",
    )
    script = admin_client.post(
        "/api/admin/slides/",
        {"slider": "sign_in", "caption": "x", "link": "javascript:alert(1)", "image": png()},
        format="multipart",
    )

    assert without.status_code == 201
    assert script.status_code == 400
    assert "link" in script.data


def test_update_without_new_image_keeps_it(admin_client):
    slide = make_slide()

    resp = admin_client.patch(
        f"/api/admin/slides/{slide.pk}/", {"is_published": True}, format="json"
    )

    slide.refresh_from_db()
    assert resp.status_code == 200
    assert slide.is_published is True
    assert slide.image.storage.exists(slide.image.name)


def test_new_slides_go_last_in_their_slider(admin_client):
    first, _ = make_slide(caption="A", position=0), make_slide(caption="B", position=1)
    make_slide(caption="Sign-in", slider="sign_in", position=7)
    admin_client.delete(f"/api/admin/slides/{first.pk}/")

    created = admin_client.post(
        "/api/admin/slides/",
        {"slider": "home_hero", "caption": "C", "image": png()},
        format="multipart",
    )
    other = admin_client.post(
        "/api/admin/slides/",
        {"caption": "D", "slider": "sign_in", "image": png()},
        format="multipart",
    )

    assert created.data["position"] == 2
    assert other.data["position"] == 8


def test_moving_a_slide_to_another_slider_puts_it_last_there(admin_client):
    slide = make_slide(caption="A", position=0)
    make_slide(caption="Safety", slider="home_safety", position=4)

    resp = admin_client.patch(
        f"/api/admin/slides/{slide.pk}/", {"slider": "home_safety"}, format="json"
    )

    assert resp.data["slider"] == "home_safety"
    assert resp.data["position"] == 5


def test_reorder_needs_every_slide_of_the_slider_once(admin_client):
    first, second = make_slide(caption="A"), make_slide(caption="B")
    other = make_slide(caption="Sign-in", slider="sign_in")
    url = "/api/admin/slides/reorder/"

    partial = admin_client.post(url, {"slider": "home_hero", "ids": [first.pk]}, format="json")
    mixed = admin_client.post(
        url, {"slider": "home_hero", "ids": [second.pk, first.pk, other.pk]}, format="json"
    )
    resp = admin_client.post(
        url, {"slider": "home_hero", "ids": [second.pk, first.pk]}, format="json"
    )

    assert partial.status_code == 400
    assert mixed.status_code == 400
    hero = [row["caption"] for row in resp.data if row["slider"] == "home_hero"]
    assert hero == ["B", "A"]


def test_public_slides_show_only_published_ones_of_the_slider(client_for):
    make_slide(caption="Live", is_published=True)
    make_slide(caption="Draft")
    make_slide(caption="Sign-in", slider="sign_in", is_published=True)

    hero = client_for().get("/api/cms/slides/", {"slider": "home_hero"})
    sign_in = client_for().get("/api/cms/slides/", {"slider": "sign_in"})

    assert [row["caption"] for row in hero.data] == ["Live"]
    assert [row["caption"] for row in sign_in.data] == ["Sign-in"]


def test_admin_can_add_the_built_in_slides_to_an_empty_slider(admin_client):
    make_slide(caption="Mine", slider="sign_in")
    url = "/api/admin/slides/add-defaults/"

    added = admin_client.post(url, {"slider": "home_safety"}, format="json")
    again = admin_client.post(url, {"slider": "home_safety"}, format="json")
    taken = admin_client.post(url, {"slider": "sign_in"}, format="json")

    assert added.status_code == 201
    safety = [row for row in added.data if row["slider"] == "home_safety"]
    assert [row["caption"] for row in safety][0] == "Check the book before you pay"
    assert all(row["is_published"] for row in safety)
    assert again.status_code == 400
    assert taken.status_code == 400


def test_seed_slides_fills_only_empty_sliders(settings):
    make_slide(caption="Mine", slider="sign_in")

    call_command("seed_slides")
    call_command("seed_slides")

    counts = {slider: Slide.objects.filter(slider=slider).count() for slider in Slide.Slider.values}
    assert counts == {"home_hero": 3, "home_safety": 3, "sign_in": 1}
    assert Slide.objects.filter(slider="home_safety", is_published=True).count() == 3


# --- Home page sections -------------------------------------------------------------------


def test_home_sections_start_in_the_home_page_order(admin_client):
    resp = admin_client.get("/api/admin/home-sections/")

    assert [row["kind"] for row in resp.data] == HomeSection.Kind.values
    assert all(row["is_enabled"] for row in resp.data)


def test_save_reorders_and_hides_sections(admin_client, client_for):
    sections = [{"kind": kind, "is_enabled": kind != "safety"} for kind in HomeSection.Kind.values]
    sections.reverse()

    saved = admin_client.put("/api/admin/home-sections/", {"sections": sections}, format="json")
    public = client_for().get("/api/cms/home-sections/")

    assert saved.status_code == 200
    assert saved.data[0]["kind"] == "call_to_action"
    assert public.data == ["call_to_action", "listing_types", "how_it_works", "hero"]


@pytest.mark.parametrize(
    "kinds",
    [["hero", "safety"], [*HomeSection.Kind.values, "hero"], [*HomeSection.Kind.values[1:], "x"]],
)
def test_save_needs_every_section_once(admin_client, kinds):
    sections = [{"kind": kind, "is_enabled": True} for kind in kinds]

    resp = admin_client.put("/api/admin/home-sections/", {"sections": sections}, format="json")

    assert resp.status_code == 400


CTA_CONTENT = {"eyebrow": "Join", "title": "Got books?", "description": "Sign up today."}

HOW_IT_WORKS_CONTENT = {
    "eyebrow": "Steps",
    "title": "How it works",
    "description": "Three steps.",
    "items": [{"title": f"Step {n}", "text": "Do it.", "note": "Easy"} for n in range(3)],
}


def test_section_content_is_saved_and_shown_publicly(admin_client, client_for):
    url = "/api/admin/home-sections/how_it_works/content/"

    saved = admin_client.put(url, HOW_IT_WORKS_CONTENT, format="json")
    listed = admin_client.get("/api/admin/home-sections/")
    public = client_for().get("/api/cms/home-content/")

    assert saved.status_code == 200
    assert saved.data["content"] == HOW_IT_WORKS_CONTENT
    assert {row["kind"]: row["content"] for row in listed.data}["hero"] == {}
    assert public.data == {"how_it_works": HOW_IT_WORKS_CONTENT}


def test_reset_goes_back_to_the_built_in_text(admin_client, client_for):
    url = "/api/admin/home-sections/call_to_action/content/"
    admin_client.put(url, CTA_CONTENT, format="json")

    reset = admin_client.delete(url)

    assert reset.data["content"] == {}
    assert client_for().get("/api/cms/home-content/").data == {}


@pytest.mark.parametrize(
    "content",
    [
        {**HOW_IT_WORKS_CONTENT, "title": ""},
        {**HOW_IT_WORKS_CONTENT, "items": HOW_IT_WORKS_CONTENT["items"][:2]},
        {**HOW_IT_WORKS_CONTENT, "items": [{"title": "No text"}] * 3},
        {**HOW_IT_WORKS_CONTENT, "description": "x" * 301},
        {**HOW_IT_WORKS_CONTENT, "items": [{"title": "Same", "text": "T", "note": "N"}] * 3},
    ],
)
def test_section_content_must_be_complete(admin_client, content):
    url = "/api/admin/home-sections/how_it_works/content/"

    assert admin_client.put(url, content, format="json").status_code == 400


def test_saving_the_order_keeps_the_content(admin_client):
    admin_client.put("/api/admin/home-sections/call_to_action/content/", CTA_CONTENT, format="json")
    sections = [{"kind": kind, "is_enabled": True} for kind in HomeSection.Kind.values]

    saved = admin_client.put("/api/admin/home-sections/", {"sections": sections}, format="json")

    assert {row["kind"]: row["content"] for row in saved.data}["call_to_action"] == CTA_CONTENT


def test_unknown_section_content_is_not_found(admin_client):
    url = "/api/admin/home-sections/footer/content/"

    assert admin_client.put(url, CTA_CONTENT, format="json").status_code == 404


def test_every_section_kind_has_editable_content():
    assert set(CONTENT_SERIALIZERS) == set(HomeSection.Kind)


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

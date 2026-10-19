import re

import pytest
from django.core import mail

from apps.accounts.models import User
from tests.conftest import PASSWORD

pytestmark = pytest.mark.django_db

REGISTER = "/api/auth/register/"
LOGIN = "/api/auth/login/"
REFRESH = "/api/auth/token/refresh/"
FRONTEND = "http://localhost:3000"


def _register(client, email="new.student@university.edu"):
    return client.post(REGISTER, {"email": email, "full_name": "New Student", "password": PASSWORD})


def _link_params(message_body):
    uid = re.search(r"uid=([^&\s]+)", message_body).group(1)
    token = re.search(r"token=([^&\s]+)", message_body).group(1)
    return {"uid": uid, "token": token}


def test_register_requires_university_email(client_for):
    resp = _register(client_for(), email="someone@gmail.com")
    assert resp.status_code == 400
    assert "email" in resp.data


def test_register_reports_weak_password_on_field(client_for):
    resp = client_for().post(
        REGISTER, {"email": "a@university.edu", "full_name": "A", "password": "12345678"}
    )
    assert resp.status_code == 400
    assert "password" in resp.data


def test_register_accepts_subdomain(client_for):
    resp = _register(client_for(), email="a.b@cs.university.edu")
    assert resp.status_code == 201


def test_register_rejects_duplicate_case_insensitive(client_for, make_user):
    make_user(email="dup@university.edu")
    assert _register(client_for(), email="DUP@university.edu").status_code == 400


def test_full_signup_verify_login_flow(client_for):
    client = client_for()
    assert _register(client).status_code == 201
    assert len(mail.outbox) == 1

    creds = {"email": "new.student@university.edu", "password": PASSWORD}
    resp = client.post(LOGIN, creds)
    assert resp.status_code == 401
    assert resp.data["code"] == "email_not_verified"

    resp = client.post("/api/auth/verify-email/", _link_params(mail.outbox[0].body))
    assert resp.status_code == 200
    assert User.objects.get(email=creds["email"]).is_email_verified

    resp = client.post(LOGIN, creds)
    assert resp.status_code == 200
    assert resp.data["email"] == creds["email"]
    assert "access" not in resp.data  # tokens only travel in httpOnly cookies
    assert resp.cookies["access_token"]["httponly"]
    assert resp.cookies["refresh_token"]["path"] == "/api/auth/"
    assert client.get("/api/auth/me/").data["email"] == creds["email"]


def test_verification_token_is_single_use(client_for):
    client = client_for()
    _register(client)
    params = _link_params(mail.outbox[0].body)
    assert client.post("/api/auth/verify-email/", params).status_code == 200
    assert client.post("/api/auth/verify-email/", params).status_code == 400


def test_me_requires_auth_and_updates_profile(client_for, make_user):
    assert client_for().get("/api/auth/me/").status_code == 401
    user = make_user()
    client = client_for(user)
    resp = client.patch("/api/auth/me/", {"department": "Physics", "email": "x@evil.com"})
    assert resp.status_code == 200
    user.refresh_from_db()
    assert user.department == "Physics"
    assert user.email != "x@evil.com"


def _login(client, user, password=PASSWORD):
    """Signs in like the browser app does and returns the refresh token that was set."""
    client.defaults["HTTP_ORIGIN"] = FRONTEND
    assert client.post(LOGIN, {"email": user.email, "password": password}).status_code == 200
    return client.cookies["refresh_token"].value


def test_refresh_rotates_cookies(client_for, make_user):
    client = client_for()
    old_refresh = _login(client, make_user())
    assert client.post(REFRESH).status_code == 204
    assert client.cookies["refresh_token"].value != old_refresh
    client.cookies["refresh_token"] = old_refresh
    assert client.post(REFRESH).status_code == 401  # rotated tokens are blacklisted


def test_refresh_without_cookie(client_for):
    assert client_for().post(REFRESH).status_code == 401


def test_logout_revokes_refresh_and_clears_cookies(client_for, make_user):
    client = client_for()
    refresh = _login(client, make_user())
    assert client.post("/api/auth/logout/").status_code == 204
    assert client.cookies["access_token"].value == ""
    client.cookies["refresh_token"] = refresh
    assert client.post(REFRESH).status_code == 401


def test_cookie_writes_require_frontend_origin(client_for, make_user):
    client = client_for()
    _login(client, make_user())
    del client.defaults["HTTP_ORIGIN"]
    url = "/api/auth/me/"
    assert client.patch(url, {"department": "Physics"}).status_code == 403
    resp = client.patch(url, {"department": "Physics"}, HTTP_ORIGIN="https://evil.example")
    assert resp.status_code == 403
    resp = client.patch(url, {"department": "Physics"}, HTTP_ORIGIN=FRONTEND)
    assert resp.status_code == 200


def test_stale_cookie_counts_as_signed_out(client_for):
    client = client_for()
    client.cookies["access_token"] = "not-a-token"
    assert client.get("/api/auth/me/").status_code == 401
    assert client.post(REFRESH).status_code == 401


def test_password_reset_flow(client_for, make_user):
    user = make_user()
    old_refresh = _login(client_for(), user)
    client = client_for()
    assert client.post("/api/auth/password/reset/", {"email": user.email}).status_code == 200
    params = _link_params(mail.outbox[-1].body)
    params["new_password"] = "An0ther-good-pass"
    assert client.post("/api/auth/password/reset/confirm/", params).status_code == 200
    _login(client, user, "An0ther-good-pass")
    client.cookies["refresh_token"] = old_refresh
    assert client.post(REFRESH).status_code == 401


def test_password_change_revokes_refresh_tokens(client_for, make_user):
    client = client_for()
    _login(client, make_user())
    resp = client.post(
        "/api/auth/password/change/",
        {"current_password": PASSWORD, "new_password": "An0ther-good-pass"},
    )
    assert resp.status_code == 200
    assert client.post(REFRESH).status_code == 401


def test_password_reset_does_not_leak_accounts(client_for):
    resp = client_for().post("/api/auth/password/reset/", {"email": "ghost@university.edu"})
    assert resp.status_code == 200
    assert len(mail.outbox) == 0

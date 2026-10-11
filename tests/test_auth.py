import re

import pytest
from django.core import mail

from apps.accounts.models import User
from tests.conftest import PASSWORD

pytestmark = pytest.mark.django_db

REGISTER = "/api/auth/register/"
LOGIN = "/api/auth/login/"


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
    assert {"access", "refresh", "user"} <= resp.data.keys()


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


def test_logout_blacklists_refresh_token(client_for, make_user):
    user = make_user()
    client = client_for()
    tokens = client.post(LOGIN, {"email": user.email, "password": PASSWORD}).data
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    assert client.post("/api/auth/logout/", {"refresh": tokens["refresh"]}).status_code == 205
    resp = client.post("/api/auth/token/refresh/", {"refresh": tokens["refresh"]})
    assert resp.status_code == 401


def test_logout_rejects_another_users_refresh_token(client_for, make_user):
    victim, attacker = make_user(), make_user()
    victim_refresh = (
        client_for().post(LOGIN, {"email": victim.email, "password": PASSWORD}).data["refresh"]
    )
    resp = client_for(attacker).post("/api/auth/logout/", {"refresh": victim_refresh})
    assert resp.status_code == 400
    resp = client_for().post("/api/auth/token/refresh/", {"refresh": victim_refresh})
    assert resp.status_code == 200


def test_password_reset_flow(client_for, make_user):
    user = make_user()
    client = client_for()
    old_refresh = client.post(LOGIN, {"email": user.email, "password": PASSWORD}).data["refresh"]
    assert client.post("/api/auth/password/reset/", {"email": user.email}).status_code == 200
    params = _link_params(mail.outbox[-1].body)
    params["new_password"] = "An0ther-good-pass"
    assert client.post("/api/auth/password/reset/confirm/", params).status_code == 200
    resp = client.post(LOGIN, {"email": user.email, "password": "An0ther-good-pass"})
    assert resp.status_code == 200
    resp = client.post("/api/auth/token/refresh/", {"refresh": old_refresh})
    assert resp.status_code == 401


def test_password_change_revokes_refresh_tokens(client_for, make_user):
    user = make_user()
    client = client_for()
    tokens = client.post(LOGIN, {"email": user.email, "password": PASSWORD}).data
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    resp = client.post(
        "/api/auth/password/change/",
        {"current_password": PASSWORD, "new_password": "An0ther-good-pass"},
    )
    assert resp.status_code == 200
    resp = client.post("/api/auth/token/refresh/", {"refresh": tokens["refresh"]})
    assert resp.status_code == 401


def test_password_reset_does_not_leak_accounts(client_for):
    resp = client_for().post("/api/auth/password/reset/", {"email": "ghost@university.edu"})
    assert resp.status_code == 200
    assert len(mail.outbox) == 0

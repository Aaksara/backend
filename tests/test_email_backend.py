from types import SimpleNamespace

import pytest
import requests
from django.core.mail import send_mail

BREVO = "utilities.email_backend.BrevoEmailBackend"


class _Response:
    def __init__(self, status_code, text=""):
        self.status_code = status_code
        self.text = text
        self.ok = status_code < 400


@pytest.fixture
def brevo(settings, monkeypatch):
    settings.EMAIL_BACKEND = BREVO
    settings.BREVO_API_KEY = "xkeysib-test"
    brevo = SimpleNamespace(calls=[], response=_Response(201, '{"messageId": "1"}'))

    def post(url, json, headers, timeout):
        brevo.calls.append({"url": url, "json": json, "headers": headers})
        return brevo.response

    monkeypatch.setattr("utilities.email_backend.requests.post", post)
    return brevo


def test_sends_through_brevo_api(brevo):
    send_mail("Hello", "Body", "Akshara <no-reply@akshara.app>", ["s@sxc.edu.np"])

    [call] = brevo.calls
    assert call["url"] == "https://api.brevo.com/v3/smtp/email"
    assert call["headers"]["api-key"] == "xkeysib-test"
    assert call["json"] == {
        "sender": {"name": "Akshara", "email": "no-reply@akshara.app"},
        "to": [{"email": "s@sxc.edu.np"}],
        "subject": "Hello",
        "textContent": "Body",
    }


def test_error_includes_brevo_reason(brevo):
    brevo.response = _Response(401, '{"message":"Key not found","code":"unauthorized"}')
    with pytest.raises(requests.HTTPError, match="Key not found"):
        send_mail("Hello", "Body", "no-reply@akshara.app", ["s@sxc.edu.np"])


@pytest.mark.django_db
def test_register_reports_brevo_failure(brevo, client_for):
    brevo.response = _Response(401, '{"message":"Key not found"}')
    resp = client_for().post(
        "/api/auth/register/",
        {"email": "a@university.edu", "full_name": "A", "password": "An0ther-good-pass"},
    )
    assert resp.status_code == 503

from email.utils import parseaddr

import requests
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

BREVO_SEND_URL = "https://api.brevo.com/v3/smtp/email"


class BrevoEmailBackend(BaseEmailBackend):
    """Sends email through Brevo's HTTP API.

    Brevo drops SMTP logins from Vercel without saying why. Its HTTP API works there,
    and an error response says what is wrong, e.g. {"message": "Key not found"}.
    """

    def send_messages(self, email_messages):
        sent = 0
        for message in email_messages:
            try:
                self._send(message)
            except requests.RequestException:
                if not self.fail_silently:
                    raise
            else:
                sent += 1
        return sent

    def _send(self, message):
        sender_name, sender_email = parseaddr(message.from_email)
        payload = {
            "sender": {"name": sender_name or sender_email, "email": sender_email},
            "to": [{"email": address} for address in message.to],
            "subject": message.subject,
            "textContent": message.body,
        }
        response = requests.post(
            BREVO_SEND_URL,
            json=payload,
            headers={"api-key": settings.BREVO_API_KEY, "Accept": "application/json"},
            timeout=settings.EMAIL_TIMEOUT,
        )
        if not response.ok:
            # HTTPError is a RequestException (and so an OSError), with Brevo's reason in it.
            raise requests.HTTPError(
                f"Brevo answered {response.status_code}: {response.text}", response=response
            )

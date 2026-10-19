import smtplib

from django.core.mail.backends import smtp


class _NoCramMd5:
    """Logs in with PLAIN or LOGIN even when the server also offers CRAM-MD5.

    smtplib tries CRAM-MD5 first when it is offered. Brevo offers it but closes the
    connection instead of answering, so the login fails with SMTPServerDisconnected.
    """

    def login(self, user, password, *, initial_response_ok=True):
        self.ehlo_or_helo_if_needed()
        methods = self.esmtp_features.get("auth", "").split()
        self.esmtp_features["auth"] = " ".join(m for m in methods if m.upper() != "CRAM-MD5")
        return super().login(user, password, initial_response_ok=initial_response_ok)


class _SMTP(_NoCramMd5, smtplib.SMTP):
    pass


class _SMTP_SSL(_NoCramMd5, smtplib.SMTP_SSL):
    pass


class EmailBackend(smtp.EmailBackend):
    """Django's SMTP backend, without CRAM-MD5."""

    @property
    def connection_class(self):
        return _SMTP_SSL if self.use_ssl else _SMTP

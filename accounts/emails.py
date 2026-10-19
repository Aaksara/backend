import logging
import smtplib

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework.exceptions import APIException

from .tokens import email_verification_token

logger = logging.getLogger(__name__)


class EmailNotSent(APIException):
    status_code = 503
    default_detail = "We could not send the email. Please try again in a few minutes."
    default_code = "email_not_sent"


def _send(user, subject, message):
    """Sends the email. Returns False, and logs why, when the mail server fails."""
    try:
        send_mail(subject=subject, message=message, from_email=None, recipient_list=[user.email])
    except (smtplib.SMTPException, OSError):
        logger.exception("Could not send %r to user %s", subject, user.pk)
        return False
    return True


def send_verification_email(user):
    token = email_verification_token.make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    link = f"{settings.FRONTEND_URL}/auth/verify-email?uid={uid}&token={token}"
    return _send(
        user,
        "Verify your AKSARA account",
        f"Hi {user.get_short_name()},\n\n"
        f"Confirm your university email to start exchanging books:\n{link}\n\n"
        "If you did not sign up, you can ignore this email.",
    )


def send_password_reset_email(user):
    token = default_token_generator.make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    link = f"{settings.FRONTEND_URL}/auth/reset-password?uid={uid}&token={token}"
    return _send(
        user,
        "Reset your AKSARA password",
        f"Hi {user.get_short_name()},\n\n"
        f"Use the link below to choose a new password:\n{link}\n\n"
        "If you did not request this, you can ignore this email.",
    )

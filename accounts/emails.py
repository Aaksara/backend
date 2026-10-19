from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .tokens import email_verification_token


def send_verification_email(user):
    token = email_verification_token.make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    link = f"{settings.FRONTEND_URL}/auth/verify-email?uid={uid}&token={token}"
    send_mail(
        subject="Verify your AKSARA account",
        message=(
            f"Hi {user.get_short_name()},\n\n"
            f"Confirm your university email to start exchanging books:\n{link}\n\n"
            "If you did not sign up, you can ignore this email."
        ),
        from_email=None,
        recipient_list=[user.email],
    )


def send_password_reset_email(user):
    token = default_token_generator.make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    link = f"{settings.FRONTEND_URL}/auth/reset-password?uid={uid}&token={token}"
    send_mail(
        subject="Reset your AKSARA password",
        message=(
            f"Hi {user.get_short_name()},\n\n"
            f"Use the link below to choose a new password:\n{link}\n\n"
            "If you did not request this, you can ignore this email."
        ),
        from_email=None,
        recipient_list=[user.email],
    )

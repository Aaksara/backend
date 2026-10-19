from django.contrib.auth.tokens import PasswordResetTokenGenerator
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken


class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    """Token invalidated as soon as the user is verified."""

    key_salt = "accounts.tokens.EmailVerificationTokenGenerator"

    def _make_hash_value(self, user, timestamp):
        return f"{user.pk}{timestamp}{user.is_email_verified}{user.email}"


email_verification_token = EmailVerificationTokenGenerator()


def revoke_refresh_tokens(user):
    """Blacklist every refresh token issued to the user, e.g. after a password change."""
    tokens = OutstandingToken.objects.filter(user=user, blacklistedtoken__isnull=True)
    BlacklistedToken.objects.bulk_create(
        [BlacklistedToken(token=token) for token in tokens], ignore_conflicts=True
    )

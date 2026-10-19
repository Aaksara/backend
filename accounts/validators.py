from django.conf import settings
from django.core.exceptions import ValidationError


def is_university_email(email: str) -> bool:
    domain = email.rsplit("@", 1)[-1].lower()
    return any(
        domain == allowed or domain.endswith("." + allowed)
        for allowed in (d.lower() for d in settings.UNIVERSITY_EMAIL_DOMAINS)
    )


def validate_university_email(email: str) -> None:
    if not is_university_email(email):
        raise ValidationError(
            "Registration is limited to university members. "
            "Please use your institutional email address."
        )

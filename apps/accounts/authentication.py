"""JWT auth for browsers: tokens live in httpOnly cookies, so page scripts never see them.

API clients can still send `Authorization: Bearer <access>` instead.
"""

from django.conf import settings
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import SAFE_METHODS
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"
# The refresh token is only needed by the auth endpoints, so only send it there.
REFRESH_COOKIE_PATH = "/api/auth/"


class CookieJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        if self.get_header(request) is not None:
            return super().authenticate(request)

        raw_token = request.COOKIES.get(ACCESS_COOKIE)
        if raw_token is None:
            return None
        try:
            token = self.get_validated_token(raw_token)
        except InvalidToken:
            return None  # A stale cookie just means "signed out".
        # Browsers send cookies automatically, so a write must come from our own frontend.
        if request.method not in SAFE_METHODS:
            if request.headers.get("Origin") not in settings.CORS_ALLOWED_ORIGINS:
                raise PermissionDenied("Request origin not allowed.")
        return self.get_user(token), token


def set_auth_cookies(response, access, refresh):
    lifetimes = settings.SIMPLE_JWT
    options = {"httponly": True, "secure": not settings.DEBUG, "samesite": "Lax"}
    response.set_cookie(
        ACCESS_COOKIE,
        str(access),
        max_age=int(lifetimes["ACCESS_TOKEN_LIFETIME"].total_seconds()),
        **options,
    )
    response.set_cookie(
        REFRESH_COOKIE,
        str(refresh),
        max_age=int(lifetimes["REFRESH_TOKEN_LIFETIME"].total_seconds()),
        path=REFRESH_COOKIE_PATH,
        **options,
    )


def clear_auth_cookies(response):
    response.delete_cookie(ACCESS_COOKIE, samesite="Lax")
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_COOKIE_PATH, samesite="Lax")

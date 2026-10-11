"""Authenticate WebSocket connections with a SimpleJWT access token.

Clients connect with `ws://host/ws/chat/<id>/?token=<access token>`.
"""

from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import AccessToken


@database_sync_to_async
def get_user_for_token(raw_token: str):
    try:
        token = AccessToken(raw_token)
    except TokenError:
        return AnonymousUser()
    User = get_user_model()
    try:
        return User.objects.get(
            **{api_settings.USER_ID_FIELD: token[api_settings.USER_ID_CLAIM]}, is_active=True
        )
    except (User.DoesNotExist, KeyError):
        return AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        query = parse_qs(scope.get("query_string", b"").decode())
        token = (query.get("token") or [None])[0]
        scope["user"] = await get_user_for_token(token) if token else AnonymousUser()
        return await super().__call__(scope, receive, send)

"""Authenticate WebSocket connections with a SimpleJWT access token.

Browsers cannot set headers on a WebSocket, so the token is sent as a subprotocol:
`new WebSocket(url, ["bearer", accessToken])`. Unlike a query string, it does not end up
in proxy access logs.
"""

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import AccessToken

SUBPROTOCOL = "bearer"


def accepted_subprotocol(scope):
    """The subprotocol to echo on accept; browsers drop the socket if it is missing."""
    return SUBPROTOCOL if SUBPROTOCOL in scope.get("subprotocols", []) else None


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
        protocols = scope.get("subprotocols", [])
        token = protocols[1] if len(protocols) == 2 and protocols[0] == SUBPROTOCOL else None
        scope["user"] = await get_user_for_token(token) if token else AnonymousUser()
        return await super().__call__(scope, receive, send)

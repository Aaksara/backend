"""Authenticate WebSocket connections with a JWT access token.

Browsers cannot set headers on a WebSocket, so clients connect with
`ws://host/ws/chat/<id>/?token=<access token>`.
"""

from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication


@database_sync_to_async
def get_user_for_token(raw_token):
    auth = JWTAuthentication()
    try:
        return auth.get_user(auth.get_validated_token(raw_token))
    except AuthenticationFailed:  # also covers invalid or expired tokens
        return AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        query = parse_qs(scope.get("query_string", b"").decode())
        token = (query.get("token") or [None])[0]
        scope["user"] = await get_user_for_token(token) if token else AnonymousUser()
        return await super().__call__(scope, receive, send)

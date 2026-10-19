import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# Initialise Django before importing anything that touches models.
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from channels.security.websocket import OriginValidator  # noqa: E402
from channels.sessions import CookieMiddleware  # noqa: E402
from django.conf import settings  # noqa: E402

from apps.chat.middleware import JWTAuthMiddleware  # noqa: E402
from apps.chat.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        # Sockets come from the browser app, so accept the same origins as CORS.
        "websocket": OriginValidator(
            CookieMiddleware(JWTAuthMiddleware(URLRouter(websocket_urlpatterns))),
            settings.CORS_ALLOWED_ORIGINS,
        ),
    }
)

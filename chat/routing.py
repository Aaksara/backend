from django.urls import path

from .consumers import ChatConsumer, InboxConsumer

websocket_urlpatterns = [
    path("ws/chat/<int:conversation_id>/", ChatConsumer.as_asgi()),
    path("ws/inbox/", InboxConsumer.as_asgi()),
]

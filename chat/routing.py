from django.urls import path
from .consumers import ChatConsumer
from .presence_consumer import PresenceConsumer

websocket_urlpatterns = [
    path("ws/chat/<str:username>/", ChatConsumer.as_asgi()),
    path("ws/presence/", PresenceConsumer.as_asgi()),
]

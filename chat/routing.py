from .presence_consumer import PresenceConsumer

websocket_urlpatterns = [
    path("ws/chat/<str:username>/", ChatConsumer.as_asgi()),   # ye already hoga
    path("ws/presence/", PresenceConsumer.as_asgi()),           # ye naya add karo
]

from django.urls import path

from . import consumers

websocket_urlpatterns = [
    path("ws/game/<uuid:game_id>/", consumers.GameConsumer.as_asgi()),
    path("ws/match/", consumers.MatchConsumer.as_asgi()),
]

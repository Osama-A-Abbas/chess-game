"""Helpers for pushing events out over the channel layer. Called from
synchronous view code after a state change has been committed."""

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .consumers import game_group, match_group


def broadcast_game_state(game_id, state):
    async_to_sync(get_channel_layer().group_send)(
        game_group(game_id), {"type": "game.update", "state": state}
    )


def notify_match_found(user_id, game_url):
    async_to_sync(get_channel_layer().group_send)(
        match_group(user_id), {"type": "match.found", "game_url": game_url}
    )

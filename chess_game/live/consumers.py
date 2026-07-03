from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer


def game_group(game_id):
    return f"game_{game_id}"


def match_group(user_id):
    return f"match_{user_id}"


class GameConsumer(AsyncJsonWebsocketConsumer):
    """One group per game. Anyone (players, spectators) may listen;
    moves themselves still go through the HTTP endpoint, which validates
    and then broadcasts the new state here."""

    async def connect(self):
        self.group = game_group(self.scope["url_route"]["kwargs"]["game_id"])
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        await self.channel_layer.group_discard(self.group, self.channel_name)

    async def game_update(self, event):
        await self.send_json(event["state"])


class MatchConsumer(AsyncJsonWebsocketConsumer):
    """Personal channel while a player waits in the quick-match queue.
    Closing the page (disconnect) removes them from the queue."""

    async def connect(self):
        user = self.scope["user"]
        if not user.is_authenticated:
            await self.close()
            return
        self.user = user
        await self.channel_layer.group_add(match_group(user.id), self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if self.scope["user"].is_authenticated:
            await self.channel_layer.group_discard(
                match_group(self.scope["user"].id), self.channel_name
            )
            await self._leave_queue()

    @database_sync_to_async
    def _leave_queue(self):
        from .models import QueueEntry

        QueueEntry.objects.filter(user=self.scope["user"]).delete()

    async def match_found(self, event):
        await self.send_json({"game_url": event["game_url"]})

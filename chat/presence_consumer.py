import json
from datetime import datetime
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
import redis


class PresenceConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]

        if not self.user.is_authenticated:
            await self.close()
            return

        await self.channel_layer.group_add("global_presence", self.channel_name)
        await self.set_online(self.user.id)

        await self.channel_layer.group_send(
            "global_presence",
            {
                "type": "presence_update",
                "user_id": self.user.id,
                "username": self.user.username,
                "status": "online"
            }
        )
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "user") and self.user.is_authenticated:
            await self.set_offline(self.user.id)
            await self.channel_layer.group_send(
                "global_presence",
                {
                    "type": "presence_update",
                    "user_id": self.user.id,
                    "username": self.user.username,
                    "status": "offline",
                    "last_seen": datetime.utcnow().isoformat()
                }
            )
            await self.channel_layer.group_discard("global_presence", self.channel_name)

    async def receive(self, text_data):
        # Client can ask "who's online right now" when the page loads
        data = json.loads(text_data)
        if data.get("type") == "get_status":
            user_ids = data.get("user_ids", [])
            statuses = await self.get_statuses(user_ids)
            await self.send(text_data=json.dumps({
                "type": "bulk_status",
                "statuses": statuses
            }))

    async def presence_update(self, event):
        await self.send(text_data=json.dumps(event))

    @database_sync_to_async
    def set_online(self, user_id):
        try:
            r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True,
                             socket_connect_timeout=1, socket_timeout=1)
            r.hset('online_users', user_id, 'online')
        except Exception:
            pass

    @database_sync_to_async
    def set_offline(self, user_id):
        try:
            r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True,
                             socket_connect_timeout=1, socket_timeout=1)
            r.hset('online_users', user_id, 'offline')
            r.hset('last_seen', user_id, datetime.utcnow().isoformat())
        except Exception:
            pass

    @database_sync_to_async
    def get_statuses(self, user_ids):
        try:
            r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True,
                             socket_connect_timeout=1, socket_timeout=1)
            result = {}
            for uid in user_ids:
                status = r.hget('online_users', uid) or 'offline'
                last_seen = r.hget('last_seen', uid)
                result[str(uid)] = {"status": status, "last_seen": last_seen}
            return result
        except Exception:
            return {}

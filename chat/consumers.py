import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from .models import Message
import redis
from datetime import datetime

User = get_user_model()


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.current_user = self.scope["user"]

        if not self.current_user.is_authenticated:
            await self.close()
            return

        self.other_username = self.scope["url_route"]["kwargs"]["username"]

        try:
            self.other_user = await database_sync_to_async(User.objects.get)(username=self.other_username)
        except User.DoesNotExist:
            await self.close()
            return

        user_ids = sorted([self.current_user.id, self.other_user.id])
        self.room_name = f"chat_{user_ids[0]}_{user_ids[1]}"
        self.room_group_name = f"chat_{self.room_name}"

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "user_status",
                "user_id": self.current_user.id,
                "username": self.current_user.username,
                "status": "online"
            }
        )

        await self.set_user_online(self.current_user.id)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "user_status",
                    "user_id": self.current_user.id,
                    "username": self.current_user.username,
                    "status": "offline",
                    "last_seen": self.get_current_time()
                }
            )
            await self.set_user_offline(self.current_user.id)
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        message_type = data.get('type')

        if message_type == 'message':
            text = data.get('text', '').strip()
            if text:
                message = await self.save_message(text)

                payload = {
                    'id': message.id,
                    'sender_id': message.sender.id,
                    'sender_username': message.sender.username,
                    'text': message.text,
                    'photo_url': message.photo.url if message.photo else None,
                    'timestamp': message.timestamp.isoformat(),
                    'is_read': message.is_read
                }

                # Broadcast to the whole room, INCLUDING the sender.
                # Frontend must dedupe using message['id'] if it also
                # does optimistic local rendering on send.
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type": "chat_message",
                        "message": payload
                    }
                )

        elif message_type == 'read':
            message_ids = data.get('message_ids', [])
            if message_ids:
                await self.mark_messages_read(message_ids)
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type": "messages_read",
                        "reader_id": self.current_user.id,
                        "message_ids": message_ids
                    }
                )

        elif message_type == 'typing':
            is_typing = data.get('is_typing', False)
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "user_typing",
                    "user_id": self.current_user.id,
                    "username": self.current_user.username,
                    "is_typing": is_typing
                }
            )

    async def chat_message(self, event):
        """Send message to WebSocket — now sent to sender too."""
        await self.send(text_data=json.dumps({
            "type": "message",
            "message": event["message"]
        }))

    async def user_status(self, event):
        if event["user_id"] != self.current_user.id:
            await self.send(text_data=json.dumps({
                "type": "user_status",
                "user_id": event["user_id"],
                "username": event["username"],
                "status": event["status"],
                "last_seen": event.get("last_seen")
            }))

    async def messages_read(self, event):
        if event["reader_id"] != self.current_user.id:
            await self.send(text_data=json.dumps({
                "type": "messages_read",
                "reader_id": event["reader_id"],
                "message_ids": event["message_ids"]
            }))

    async def user_typing(self, event):
        if event["user_id"] != self.current_user.id:
            await self.send(text_data=json.dumps({
                "type": "typing",
                "user_id": event["user_id"],
                "username": event["username"],
                "is_typing": event["is_typing"]
            }))

    @database_sync_to_async
    def save_message(self, text):
        return Message.objects.create(
            sender=self.current_user,
            receiver=self.other_user,
            text=text
        )

    @database_sync_to_async
    def mark_messages_read(self, message_ids):
        Message.objects.filter(
            id__in=message_ids,
            receiver=self.current_user,
            sender=self.other_user,
            is_read=False
        ).update(is_read=True)

    @database_sync_to_async
    def set_user_online(self, user_id):
        try:
            r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True,
                             socket_connect_timeout=1, socket_timeout=1)
            r.hset('online_users', user_id, 'online')
            r.sadd(f'user_rooms:{user_id}', self.room_group_name)
        except Exception:
            pass

    @database_sync_to_async
    def set_user_offline(self, user_id):
        try:
            r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True,
                             socket_connect_timeout=1, socket_timeout=1)
            r.hset('online_users', user_id, 'offline')
            r.hset('last_seen', user_id, datetime.utcnow().isoformat())
            r.srem(f'user_rooms:{user_id}', self.room_group_name)
        except Exception:
            pass

    def get_current_time(self):
        return datetime.utcnow().isoformat()

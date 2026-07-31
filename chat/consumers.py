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
        print(f'WebSocket connect attempt: user={self.scope["user"]}')
        self.current_user = self.scope["user"]
        
        if not self.current_user.is_authenticated:
            print('User not authenticated, closing')
            await self.close()
            return

        # Get the other user from URL
        self.other_username = self.scope["url_route"]["kwargs"]["username"]
        print(f'Other username: {self.other_username}')
        
        try:
            self.other_user = await database_sync_to_async(User.objects.get)(username=self.other_username)
            print(f'Found other user: {self.other_user}')
        except User.DoesNotExist:
            print('Other user does not exist, closing')
            await self.close()
            return

        # Create a unique room name for this conversation (sorted to be consistent)
        user_ids = sorted([self.current_user.id, self.other_user.id])
        self.room_name = f"chat_{user_ids[0]}_{user_ids[1]}"
        self.room_group_name = f"chat_{self.room_name}"
        print(f'Room group name: {self.room_group_name}')

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        print('Joined room group')

        # Notify others that user is online
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "user_status",
                "user_id": self.current_user.id,
                "username": self.current_user.username,
                "status": "online"
            }
        )
        print('Sent user_status')

        # Update user's online status in Redis (non-blocking)
        await self.set_user_online(self.current_user.id)
        print('Set user online')

        await self.accept()
        print('Connection accepted')

    async def disconnect(self, close_code):
        print(f'Disconnect: {close_code}')
        if hasattr(self, 'room_group_name'):
            # Notify others that user is offline
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

            # Update user's offline status in Redis with last seen time
            await self.set_user_offline(self.current_user.id)

            # Leave room group
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        print(f'Received: {text_data}')
        data = json.loads(text_data)
        message_type = data.get('type')
        
        if message_type == 'message':
            text = data.get('text', '').strip()
            if text:
                # Save message to database
                message = await self.save_message(text)
                
                # Broadcast message to room group
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type": "chat_message",
                        "message": {
                            'id': message.id,
                            'sender_id': message.sender.id,
                            'sender_username': message.sender.username,
                            'text': message.text,
                            'photo_url': message.photo.url if message.photo else None,
                            'timestamp': message.timestamp.isoformat(),
                            'is_read': message.is_read
                        }
                    }
                )
        
        elif message_type == 'read':
            message_ids = data.get('message_ids', [])
            if message_ids:
                await self.mark_messages_read(message_ids)
                
                # Notify sender that messages were read
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
            # Broadcast typing status to other user
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
        """Receive message from room group and send to WebSocket"""
        message = event["message"]
        # Don't send back to sender if they already have it
        if message["sender_id"] != self.current_user.id:
            await self.send(text_data=json.dumps({
                "type": "message",
                "message": message
            }))

    async def user_status(self, event):
        """Send user online/offline status to WebSocket"""
        if event["user_id"] != self.current_user.id:
            await self.send(text_data=json.dumps({
                "type": "user_status",
                "user_id": event["user_id"],
                "username": event["username"],
                "status": event["status"],
                "last_seen": event.get("last_seen")
            }))

    async def messages_read(self, event):
        """Notify that messages were read"""
        if event["reader_id"] != self.current_user.id:
            await self.send(text_data=json.dumps({
                "type": "messages_read",
                "reader_id": event["reader_id"],
                "message_ids": event["message_ids"]
            }))

    async def user_typing(self, event):
        """Notify that user is typing"""
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
            r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True, socket_connect_timeout=1, socket_timeout=1)
            r.hset('online_users', user_id, 'online')
            r.sadd(f'user_rooms:{user_id}', self.room_group_name)
        except Exception:
            # Redis not available, skip
            pass

    @database_sync_to_async
    def set_user_offline(self, user_id):
        try:
            r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True, socket_connect_timeout=1, socket_timeout=1)
            r.hset('online_users', user_id, 'offline')
            r.hset('last_seen', user_id, datetime.utcnow().isoformat())
            r.srem(f'user_rooms:{user_id}', self.room_group_name)
        except Exception:
            # Redis not available, skip
            pass

    def get_current_time(self):
        return datetime.utcnow().isoformat()
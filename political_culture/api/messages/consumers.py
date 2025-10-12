import json
import logging

from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger(__name__)


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user_id = self.scope["url_route"]["kwargs"]["userId"]
        self.room_group_name = f"chat_{self.user_id}"

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)

        await self.accept()
        logger.info(f"WebSocket connected for user {self.user_id}")

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
        logger.info(f"WebSocket disconnected for user {self.user_id}")

    async def receive(self, text_data):
        pass

    async def chat_message(self, event):
        message = event["message"]
        await self.send(text_data=json.dumps(message))

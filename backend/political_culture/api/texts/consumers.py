import json
import logging
from typing import Any

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from backend.api_auth import websocket_user_id

logger = logging.getLogger(__name__)


class TextsConsumer(AsyncWebsocketConsumer):  # type: ignore[misc]
    """Tells the user how each of their uploads ended (texts/service.py)."""

    group_name: str | None = None

    async def connect(self) -> None:
        user_id = self.scope["url_route"]["kwargs"]["userId"]

        if (
            await database_sync_to_async(websocket_user_id)(
                self.scope, "political-culture"
            )
            != user_id
        ):
            logger.info(f"Texts socket rejected for user {user_id}")
            await self.close()
            return

        self.group_name = f"texts_{user_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept(subprotocol="bearer")

    async def disconnect(self, close_code: int) -> None:
        if self.group_name:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def upload_result(self, event: dict[str, Any]) -> None:
        await self.send(text_data=json.dumps(event["result"]))

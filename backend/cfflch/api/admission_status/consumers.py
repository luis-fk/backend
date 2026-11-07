import json

from channels.generic.websocket import AsyncWebsocketConsumer


class AdmissionStatusConsumer(AsyncWebsocketConsumer):  # type: ignore[misc]
    async def connect(self) -> None:
        self.request_id = self.scope["url_route"]["kwargs"]["requestId"]
        self.group_name = f"admission_status_{self.request_id}"

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code: int) -> None:
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data: str) -> None:
        pass

    async def admission_status_message(self, event: dict[str, str]) -> None:
        message = event["message"]
        await self.send(text_data=json.dumps(message))

    async def admission_status_done(self, event: dict[str, str]) -> None:
        await self.send(text_data=json.dumps({"done": True}))

import logging
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

API_ROOT = "https://api.telegram.org"
MESSAGE_LIMIT = 4096
UPLOAD_TIMEOUT_SECONDS = 300.0
DEFAULT_TIMEOUT_SECONDS = 60.0


class TelegramError(Exception):
    pass


class TelegramClient:
    def __init__(self, http_client: httpx.AsyncClient, token: str) -> None:
        self.http_client = http_client
        self.token = token

    async def send_voice(
        self, chat_id: str, voice_path: Path, caption: str, duration_seconds: int
    ) -> None:
        await self._call(
            "sendVoice",
            data={
                "chat_id": chat_id,
                "caption": caption,
                "parse_mode": "HTML",
                "duration": str(duration_seconds),
            },
            files={"voice": (voice_path.name, voice_path.read_bytes(), "audio/ogg")},
            timeout=UPLOAD_TIMEOUT_SECONDS,
        )
        logger.info(f"Sent {voice_path.name} to Telegram")

    async def send_message(self, chat_id: str, text: str) -> None:
        await self._call(
            "sendMessage",
            data={
                "chat_id": chat_id,
                "text": text[:MESSAGE_LIMIT],
                "parse_mode": "HTML",
                "link_preview_options": '{"is_disabled": true}',
            },
        )

    async def recent_private_chat_ids(self) -> list[str]:
        updates = await self._call("getUpdates", data={"timeout": "0"})
        chat_ids: list[str] = []
        for update in updates if isinstance(updates, list) else []:
            message = update.get("message") or update.get("my_chat_member") or {}
            chat = message.get("chat") or {}
            chat_id = str(chat.get("id", ""))
            if chat.get("type") == "private" and chat_id and chat_id not in chat_ids:
                chat_ids.append(chat_id)
        return chat_ids

    async def _call(
        self,
        method: str,
        data: dict[str, str],
        files: dict[str, tuple[str, bytes, str]] | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> Any:
        try:
            response = await self.http_client.post(
                f"{API_ROOT}/bot{self.token}/{method}",
                data=data,
                files=files,
                timeout=timeout,
            )
        except httpx.HTTPError as error:
            raise TelegramError(
                f"Telegram {method}: {self._redact(str(error))}"
            ) from error

        try:
            payload = response.json()
        except ValueError:
            payload = {}

        if response.status_code != 200 or not payload.get("ok"):
            description = payload.get("description", f"HTTP {response.status_code}")
            raise TelegramError(f"Telegram {method}: {self._redact(str(description))}")
        return payload.get("result")

    def _redact(self, text: str) -> str:
        return text.replace(self.token, "***") if self.token else text

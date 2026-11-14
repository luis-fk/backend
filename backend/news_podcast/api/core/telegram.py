import logging
from pathlib import Path
from typing import Any

import httpx
from django.conf import settings

from news_podcast.api.core.messages import (
    chat_id_message,
    chat_list_message,
    failure_message,
)
from news_podcast.api.core.schemas import TelegramChat

logger = logging.getLogger(__name__)

API_ROOT = "https://api.telegram.org"
MESSAGE_LIMIT = 4096
UPLOAD_TIMEOUT_SECONDS = 300.0
DEFAULT_TIMEOUT_SECONDS = 60.0
CHAT_TYPES = frozenset({"private", "group", "supergroup"})
GONE_STATUSES = frozenset({"left", "kicked"})


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

    async def recent_chats(self) -> list[TelegramChat]:
        updates = await self._call("getUpdates", data={"timeout": "0"})
        chats: dict[str, TelegramChat] = {}
        for update in updates if isinstance(updates, list) else []:
            membership = update.get("my_chat_member") or {}
            event = update.get("message") or membership
            chat = event.get("chat") or {}
            chat_id = str(chat.get("id", ""))
            if not chat_id or chat.get("type") not in CHAT_TYPES:
                continue

            status = (membership.get("new_chat_member") or {}).get("status")
            if status in GONE_STATUSES or event.get("migrate_to_chat_id"):
                chats.pop(chat_id, None)
            else:
                chats[chat_id] = TelegramChat(
                    id=chat_id,
                    name=chat_name(chat),
                    is_group=chat["type"] != "private",
                )
        return list(chats.values())

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


def chat_name(chat: dict[str, Any]) -> str:
    if chat.get("type") != "private":
        return str(chat.get("title") or "Grupo sem nome")
    full_name = " ".join(
        str(part) for part in (chat.get("first_name"), chat.get("last_name")) if part
    )
    return full_name or str(chat.get("username") or "Conversa sem nome")


async def send_chat_ids(
    telegram: TelegramClient | None, admin_chat_id: str | None
) -> int:
    """Sends the list of the chats the bot saw to the admin chat. On the first setup,
    with no chat configured, sends each chat its own id instead."""
    if telegram is None:
        raise TelegramError("TELEGRAM_BOT_TOKEN não configurado")

    chats = await telegram.recent_chats()
    if not chats:
        raise TelegramError(
            "Nenhuma conversa encontrada. Mande /start para o bot ou adicione ele "
            "a um grupo no Telegram e rode de novo."
        )
    if admin_chat_id:
        await telegram.send_message(admin_chat_id, chat_list_message(chats))
        return len(chats)

    for chat in chats:
        await telegram.send_message(chat.id, chat_id_message(chat.id))
    return len(chats)


async def notify_failure(
    telegram: TelegramClient | None,
    chat_id: str | None,
    subject: str,
    step: str,
    error: Exception,
) -> None:
    if telegram is None or not chat_id:
        return
    try:
        await telegram.send_message(chat_id, failure_message(subject, step, error))
    except TelegramError as notify_error:
        logger.error(f"Could not report the failure on Telegram: {notify_error}")


def chat_id() -> str | None:
    return getattr(settings, "TELEGRAM_CHAT_ID", None) or None


def admin_chat_id() -> str | None:
    return getattr(settings, "TELEGRAM_ADMIN_CHAT_ID", None) or chat_id()


def telegram_client(http_client: httpx.AsyncClient) -> TelegramClient | None:
    bot_token = getattr(settings, "TELEGRAM_BOT_TOKEN", None)
    return TelegramClient(http_client, bot_token) if bot_token else None


async def report_failure(subject: str, step: str, error: Exception) -> None:
    async with httpx.AsyncClient() as http_client:
        await notify_failure(
            telegram_client(http_client), admin_chat_id(), subject, step, error
        )


async def report_chat_ids() -> None:
    async with httpx.AsyncClient() as http_client:
        found = await send_chat_ids(telegram_client(http_client), admin_chat_id())
    logger.info(f"Reported the ids of {found} chat(s)")

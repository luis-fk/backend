import asyncio
from pathlib import Path

import httpx
import pytest

from news_podcast.api.core.schemas import (
    TelegramChat,
)
from news_podcast.api.core.telegram import (
    TelegramClient,
    TelegramError,
    send_chat_ids,
)


def test_send_voice_uploads_an_ogg_voice_message(tmp_path: Path) -> None:
    voice = tmp_path / "resumo.ogg"
    voice.write_bytes(b"OggS")
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"ok": True, "result": {"voice": {}}})

    async def scenario() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await TelegramClient(client, "TOKEN").send_voice(
                "42", voice, "<b>Resumo</b>", 600
            )

    asyncio.run(scenario())

    request = requests[0]
    assert request.url.path == "/botTOKEN/sendVoice"
    assert b'name="voice"; filename="resumo.ogg"' in request.content
    assert b"Content-Type: audio/ogg" in request.content
    assert b'name="duration"\r\n\r\n600' in request.content


def test_recent_chats_include_groups_and_drop_the_ones_the_bot_left() -> None:
    felipe = {"id": 11, "type": "private", "first_name": "Felipe", "last_name": "K"}
    updates = [
        {"message": {"chat": felipe}},
        {
            "my_chat_member": {
                "chat": {"id": -22, "type": "group", "title": "Resumo"},
                "new_chat_member": {"status": "member"},
            }
        },
        {
            "my_chat_member": {
                "chat": {"id": -33, "type": "group", "title": "Antigo"},
                "new_chat_member": {"status": "left"},
            }
        },
        {
            "message": {
                "chat": {"id": -44, "type": "group", "title": "Família"},
                "migrate_to_chat_id": -10044,
            }
        },
        {"message": {"chat": {"id": -10044, "type": "supergroup", "title": "Família"}}},
        {"channel_post": {"chat": {"id": -55, "type": "channel", "title": "Canal"}}},
        {"message": {"chat": felipe}},
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True, "result": updates})

    async def scenario() -> list[TelegramChat]:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await TelegramClient(client, "TOKEN").recent_chats()

    assert asyncio.run(scenario()) == [
        TelegramChat(id="11", name="Felipe K", is_group=False),
        TelegramChat(id="-22", name="Resumo", is_group=True),
        TelegramChat(id="-10044", name="Família", is_group=True),
    ]


CHATS = [
    TelegramChat(id="11", name="Felipe", is_group=False),
    TelegramChat(id="-22", name="Resumo & cia", is_group=True),
]


class FakeTelegram(TelegramClient):
    def __init__(self, http_client: httpx.AsyncClient) -> None:
        super().__init__(http_client, "TOKEN")
        self.sent: list[tuple[str, str]] = []
        self.chats = list(CHATS)

    async def recent_chats(self) -> list[TelegramChat]:
        return self.chats

    async def send_message(self, chat_id: str, text: str) -> None:
        self.sent.append((chat_id, text))

    async def send_voice(
        self, chat_id: str, voice_path: Path, caption: str, duration_seconds: int
    ) -> None:
        self.sent.append((chat_id, caption))


async def report_chats(admin_chat_id: str | None) -> list[tuple[str, str]]:
    async with httpx.AsyncClient() as client:
        telegram = FakeTelegram(client)
        await send_chat_ids(telegram, admin_chat_id)
        return telegram.sent


def test_chat_list_goes_only_to_the_admin_chat() -> None:
    sent = asyncio.run(report_chats(admin_chat_id="11"))

    assert [chat_id for chat_id, _ in sent] == ["11"]
    assert "👤 Felipe: <code>11</code>" in sent[0][1]
    assert "👥 Resumo &amp; cia: <code>-22</code>" in sent[0][1]


def test_first_setup_sends_each_chat_its_own_id() -> None:
    sent = asyncio.run(report_chats(admin_chat_id=None))

    assert [chat_id for chat_id, _ in sent] == ["11", "-22"]
    assert all(f"<code>{chat_id}</code>" in text for chat_id, text in sent)


def test_the_chat_list_needs_the_bot_token() -> None:
    with pytest.raises(TelegramError, match="TELEGRAM_BOT_TOKEN não configurado"):
        asyncio.run(send_chat_ids(None, "11"))


def test_the_chat_list_needs_a_chat_the_bot_saw() -> None:
    async def scenario() -> None:
        async with httpx.AsyncClient() as client:
            telegram = FakeTelegram(client)
            telegram.chats = []
            await send_chat_ids(telegram, "11")

    with pytest.raises(TelegramError, match="Nenhuma conversa encontrada"):
        asyncio.run(scenario())

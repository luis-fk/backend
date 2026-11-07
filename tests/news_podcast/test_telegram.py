import asyncio
from pathlib import Path

import httpx

from news_podcast.api.episode.schemas import TelegramChat
from news_podcast.api.episode.telegram import TelegramClient


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

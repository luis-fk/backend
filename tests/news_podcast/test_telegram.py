import asyncio
from pathlib import Path

import httpx

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

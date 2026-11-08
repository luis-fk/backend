import asyncio
from collections.abc import Sequence
from datetime import date, datetime, time
from pathlib import Path
from typing import Any

import httpx
import pytest

from news_podcast.api.episode import config
from news_podcast.api.episode.gemini import (
    GeminiClient,
    GeminiQuotaExhaustedError,
    GeminiUnavailableError,
)
from news_podcast.api.episode.schemas import (
    EpisodeOptions,
    EpisodeReport,
    Host,
    TelegramChat,
    Turn,
    Usage,
)
from news_podcast.api.episode.service import (
    EpisodeError,
    NewsPodcastService,
    script_prompt,
    selection_prompt,
)
from news_podcast.api.episode.telegram import TelegramClient

TURNS = [Turn(speaker="Bia", text="Bom dia")]
DEFAULT_OPTIONS = EpisodeOptions(12, 18, time(7, 0), 1.0)
CHATS = [
    TelegramChat(id="11", name="Felipe", is_group=False),
    TelegramChat(id="-22", name="Resumo & cia", is_group=True),
]


class FakeGemini(GeminiClient):
    def __init__(
        self, http_client: httpx.AsyncClient, voice_failures: list[Exception]
    ) -> None:
        super().__init__(http_client, "key")
        self.voice_failures = voice_failures
        self.text_models: list[str] = []

    async def generate_json(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        step: str,
        thinking_level: str | None = None,
    ) -> tuple[Any, Usage]:
        self.text_models.append(model)
        if model == config.TEXT_MODEL:
            raise GeminiUnavailableError("Gemini respondeu 503: high demand")
        return {"ok": True}, Usage(step=step, model=model)

    async def synthesize_dialogue(
        self, model: str, turns: list[Turn], hosts: Sequence[Host], step: str
    ) -> tuple[bytes, Usage]:
        if self.voice_failures:
            raise self.voice_failures.pop(0)
        return b"audio", Usage(step=step, model=model)


def make_service(
    http_client: httpx.AsyncClient, gemini: GeminiClient
) -> NewsPodcastService:
    return NewsPodcastService(
        http_client=http_client,
        gemini=gemini,
        telegram=None,
        chat_id=None,
        options=DEFAULT_OPTIONS,
    )


def record_waits(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    waits: list[float] = []

    async def record(seconds: float) -> None:
        waits.append(seconds)

    monkeypatch.setattr(asyncio, "sleep", record)
    return waits


async def synthesize_with(failures: list[Exception]) -> list[int]:
    async with httpx.AsyncClient() as client:
        gemini = FakeGemini(client, voice_failures=failures)
        service = make_service(client, gemini)
        await service._synthesize_patiently(gemini, TURNS)
        return service.voice_retry_minutes


def test_text_skips_the_main_model_once_it_is_unavailable() -> None:
    async def scenario() -> list[str]:
        async with httpx.AsyncClient() as client:
            gemini = FakeGemini(client, voice_failures=[])
            service = make_service(client, gemini)
            for step in ("selection", "script"):
                await service._ask_json("system", "user", step, lambda data: data)
            return gemini.text_models

    models = asyncio.run(scenario())

    assert models == [
        config.TEXT_MODEL,
        config.TEXT_FALLBACK_MODEL,
        config.TEXT_FALLBACK_MODEL,
    ]


def test_voice_waits_and_tries_again_when_gemini_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    waits = record_waits(monkeypatch)

    remaining = asyncio.run(synthesize_with([GeminiUnavailableError("503")]))

    assert waits == [config.VOICE_RETRY_MINUTES[0] * 60]
    assert remaining == list(config.VOICE_RETRY_MINUTES[1:])


def test_voice_gives_up_after_the_last_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    waits = record_waits(monkeypatch)
    retries = len(config.VOICE_RETRY_MINUTES)
    failures: list[Exception] = [GeminiUnavailableError("503")] * (retries + 1)

    with pytest.raises(GeminiUnavailableError):
        asyncio.run(synthesize_with(failures))

    assert waits == [minutes * 60 for minutes in config.VOICE_RETRY_MINUTES]


def test_voice_does_not_wait_when_the_daily_quota_is_over(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    waits = record_waits(monkeypatch)

    with pytest.raises(GeminiQuotaExhaustedError):
        asyncio.run(synthesize_with([GeminiQuotaExhaustedError("429")]))

    assert waits == []


def test_prompts_follow_the_configured_options() -> None:
    options = EpisodeOptions(20, 30, time(21, 0), 1.0)
    start = datetime(2026, 11, 6, 20, 0, tzinfo=config.LOCAL_TZ)
    end = datetime(2026, 11, 7, 20, 0, tzinfo=config.LOCAL_TZ)

    selection = selection_prompt(options, start, end)
    script = script_prompt(options, date(2026, 11, 7), start, end)

    assert "em 20 a 30 minutos" in selection
    assert "Escolha de 13 a 20 histórias" in selection
    assert 'chamado "Resumo das 21"' in script
    assert "O episódio sai às 21h de sábado, 7 de novembro" in script
    assert "uma fala curta com boa noite e a data" in script
    assert "entre 3400 e 5100 palavras" in script


def test_default_prompts_keep_the_morning_episode() -> None:
    start = datetime(2026, 11, 5, 6, 0, tzinfo=config.LOCAL_TZ)
    end = datetime(2026, 11, 6, 6, 0, tzinfo=config.LOCAL_TZ)

    selection = selection_prompt(DEFAULT_OPTIONS, start, end)
    script = script_prompt(DEFAULT_OPTIONS, date(2026, 11, 6), start, end)

    assert "Escolha de 8 a 12 histórias" in selection
    assert 'chamado "Resumo das 7"' in script
    assert "O episódio sai às 7h de sexta-feira, 6 de novembro" in script
    assert "uma fala curta com bom dia e a data" in script
    assert "entre 2040 e 3060 palavras" in script


class FakeTelegram(TelegramClient):
    def __init__(self, http_client: httpx.AsyncClient) -> None:
        super().__init__(http_client, "TOKEN")
        self.sent: list[tuple[str, str]] = []

    async def recent_chats(self) -> list[TelegramChat]:
        return CHATS

    async def send_message(self, chat_id: str, text: str) -> None:
        self.sent.append((chat_id, text))

    async def send_voice(
        self, chat_id: str, voice_path: Path, caption: str, duration_seconds: int
    ) -> None:
        self.sent.append((chat_id, caption))


def telegram_service(
    client: httpx.AsyncClient,
    telegram: TelegramClient,
    chat_id: str | None,
    admin_chat_id: str | None = None,
) -> NewsPodcastService:
    return NewsPodcastService(
        http_client=client,
        gemini=None,
        telegram=telegram,
        chat_id=chat_id,
        options=DEFAULT_OPTIONS,
        admin_chat_id=admin_chat_id,
    )


async def report_chats(
    chat_id: str | None, admin_chat_id: str | None = None
) -> list[tuple[str, str]]:
    async with httpx.AsyncClient() as client:
        telegram = FakeTelegram(client)
        await telegram_service(client, telegram, chat_id, admin_chat_id).send_chat_ids()
        return telegram.sent


def test_episode_goes_out_as_a_single_voice_message(tmp_path: Path) -> None:
    report = EpisodeReport(
        audio_path=tmp_path / "resumo.ogg",
        duration_seconds=600.4,
        caption="🎙️ Resumo das 7",
    )

    async def scenario() -> list[tuple[str, str]]:
        async with httpx.AsyncClient() as client:
            telegram = FakeTelegram(client)
            await telegram_service(client, telegram, "-22")._deliver(report)
            return telegram.sent

    assert asyncio.run(scenario()) == [("-22", "🎙️ Resumo das 7")]


def test_chat_list_goes_only_to_the_configured_chat() -> None:
    sent = asyncio.run(report_chats(chat_id="11"))

    assert [chat_id for chat_id, _ in sent] == ["11"]
    assert "👤 Felipe: <code>11</code>" in sent[0][1]
    assert "👥 Resumo &amp; cia: <code>-22</code>" in sent[0][1]


def test_chat_list_goes_to_the_admin_chat_when_there_is_one() -> None:
    sent = asyncio.run(report_chats(chat_id="-22", admin_chat_id="11"))

    assert [chat_id for chat_id, _ in sent] == ["11"]


def test_errors_go_to_the_admin_chat_not_the_group(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fail(*_args: object) -> None:
        raise EpisodeError("sem histórias")

    async def scenario() -> list[tuple[str, str]]:
        async with httpx.AsyncClient() as client:
            telegram = FakeTelegram(client)
            service = telegram_service(client, telegram, "-22", admin_chat_id="11")
            monkeypatch.setattr(service, "_generate", fail)
            with pytest.raises(EpisodeError):
                await service.generate_episode(scheduled=False, send=True)
            return telegram.sent

    assert [chat_id for chat_id, _ in asyncio.run(scenario())] == ["11"]


def test_first_setup_sends_each_chat_its_own_id() -> None:
    sent = asyncio.run(report_chats(chat_id=None))

    assert [chat_id for chat_id, _ in sent] == ["11", "-22"]
    assert all(f"<code>{chat_id}</code>" in text for chat_id, text in sent)

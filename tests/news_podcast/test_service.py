import asyncio
from collections.abc import Sequence
from typing import Any

import httpx
import pytest

from news_podcast.api.episode import config
from news_podcast.api.episode.gemini import (
    GeminiClient,
    GeminiQuotaExhaustedError,
    GeminiUnavailableError,
)
from news_podcast.api.episode.schemas import Host, Turn, Usage
from news_podcast.api.episode.service import NewsPodcastService

TURNS = [Turn(speaker="Bia", text="Bom dia")]


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
        voice="gemini-flash-lite",
        plan="free",
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
        await service._synthesize_patiently(gemini, "tts", TURNS)
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

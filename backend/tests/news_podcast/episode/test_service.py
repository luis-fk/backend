import asyncio
from collections.abc import Sequence
from pathlib import Path

import httpx
import pytest
from langchain_core.language_models import BaseChatModel
from pytest_django import Settings

from news_podcast.api.core import config as core_config
from news_podcast.api.core.gemini import (
    GeminiClient,
    GeminiQuotaExhaustedError,
    GeminiUnavailableError,
)
from news_podcast.api.core.llm import TextError
from news_podcast.api.core.schemas import (
    Host,
    Turn,
    Usage,
)
from news_podcast.api.core.telegram import (
    TelegramClient,
    TelegramError,
)
from news_podcast.api.episode import service as service_module
from news_podcast.api.episode.run import episode_settings
from news_podcast.api.episode.schemas import (
    EpisodeReport,
    NewsItem,
)
from news_podcast.api.episode.service import (
    EpisodeError,
    EpisodeService,
)
from news_podcast.models import PodcastSettings

TURNS = [Turn(speaker="Bia", text="Bom dia")]


class FakeGemini(GeminiClient):
    """The voice fails with `voice_failures`, in order, and then answers."""

    def __init__(
        self, http_client: httpx.AsyncClient, voice_failures: list[Exception]
    ) -> None:
        super().__init__(http_client, "key")
        self.voice_failures = voice_failures

    async def synthesize_dialogue(
        self,
        model: str,
        turns: list[Turn],
        hosts: Sequence[Host],
        step: str,
        *,
        style: str,
        headline_style: str,
    ) -> tuple[bytes, Usage]:
        if self.voice_failures:
            raise self.voice_failures.pop(0)
        return b"audio", Usage(step=step, model=model)


def make_service(
    http_client: httpx.AsyncClient, gemini: GeminiClient
) -> EpisodeService:
    return EpisodeService(
        http_client=http_client,
        gemini=gemini,
        telegram=None,
        chat_id=None,
        settings=episode_settings(PodcastSettings()),
        sources=[],
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


def test_voice_waits_and_tries_again_when_gemini_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    waits = record_waits(monkeypatch)

    remaining = asyncio.run(synthesize_with([GeminiUnavailableError("503")]))

    assert waits == [core_config.VOICE_RETRY_MINUTES[0] * 60]
    assert remaining == list(core_config.VOICE_RETRY_MINUTES[1:])


def test_voice_gives_up_after_the_last_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    waits = record_waits(monkeypatch)
    retries = len(core_config.VOICE_RETRY_MINUTES)
    failures: list[Exception] = [GeminiUnavailableError("503")] * (retries + 1)

    with pytest.raises(GeminiUnavailableError):
        asyncio.run(synthesize_with(failures))

    assert waits == [minutes * 60 for minutes in core_config.VOICE_RETRY_MINUTES]


def test_voice_does_not_wait_when_the_daily_quota_is_over(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    waits = record_waits(monkeypatch)

    with pytest.raises(GeminiQuotaExhaustedError):
        asyncio.run(synthesize_with([GeminiQuotaExhaustedError("429")]))

    assert waits == []


class FakeTelegram(TelegramClient):
    def __init__(self, http_client: httpx.AsyncClient) -> None:
        super().__init__(http_client, "TOKEN")
        self.sent: list[tuple[str, str]] = []

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
) -> EpisodeService:
    return EpisodeService(
        http_client=client,
        gemini=None,
        telegram=telegram,
        chat_id=chat_id,
        settings=episode_settings(PodcastSettings()),
        sources=[],
        admin_chat_id=admin_chat_id,
    )


def test_episode_goes_out_as_a_single_voice_message(tmp_path: Path) -> None:
    report = EpisodeReport(
        audio_path=tmp_path / "resumo.ogg",
        duration_seconds=600.4,
        caption="🎙️ Resumo das 7",
        script_words=1700,
    )

    async def scenario() -> list[tuple[str, str]]:
        async with httpx.AsyncClient() as client:
            telegram = FakeTelegram(client)
            await telegram_service(client, telegram, "-22")._deliver(report)
            return telegram.sent

    assert asyncio.run(scenario()) == [("-22", "🎙️ Resumo das 7")]


def test_a_scheduled_episode_goes_out_as_soon_as_it_is_ready(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    report = EpisodeReport(
        audio_path=tmp_path / "resumo.ogg",
        duration_seconds=600.4,
        caption="🎙️ Resumo das 7",
        script_words=1700,
    )
    waits = record_waits(monkeypatch)

    async def ready(*_args: object) -> EpisodeReport:
        return report

    async def scenario() -> list[tuple[str, str]]:
        async with httpx.AsyncClient() as client:
            telegram = FakeTelegram(client)
            service = telegram_service(client, telegram, "-22")
            monkeypatch.setattr(service, "_generate", ready)
            await service.generate_episode(scheduled=True, send=True)
            return telegram.sent

    assert asyncio.run(scenario()) == [("-22", "🎙️ Resumo das 7")]
    assert waits == []


class RefusingTelegram(FakeTelegram):
    """Refuses the voice message, as a group does when the bot can't post in it."""

    async def send_voice(
        self, chat_id: str, voice_path: Path, caption: str, duration_seconds: int
    ) -> None:
        raise TelegramError("Telegram respondeu 400: not enough rights")


def test_a_refused_send_warns_the_admin_chat(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    report = EpisodeReport(
        audio_path=tmp_path / "resumo.ogg",
        duration_seconds=600.4,
        caption="🎙️ Resumo das 7",
        script_words=1700,
    )

    async def ready(*_args: object) -> EpisodeReport:
        return report

    async def scenario() -> list[tuple[str, str]]:
        async with httpx.AsyncClient() as client:
            telegram = RefusingTelegram(client)
            service = telegram_service(client, telegram, "-22", admin_chat_id="11")
            monkeypatch.setattr(service, "_generate", ready)
            with pytest.raises(TelegramError):
                await service.generate_episode(scheduled=True, send=True)
            return telegram.sent

    sent = asyncio.run(scenario())

    assert [chat_id for chat_id, _ in sent] == ["11"]
    assert "<b>Etapa:</b> envio" in sent[0][1]


def test_a_run_past_the_time_limit_stops_and_warns_the_admin_chat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("news_podcast.api.episode.service.MAX_RUN_MINUTES", 0.001)

    async def scenario() -> list[tuple[str, str]]:
        async with httpx.AsyncClient() as client:
            telegram = FakeTelegram(client)
            service = telegram_service(client, telegram, "-22", admin_chat_id="11")

            async def stuck(*_args: object) -> EpisodeReport:
                service.step = "montagem do áudio"
                await asyncio.Event().wait()
                raise AssertionError("unreachable")

            monkeypatch.setattr(service, "_generate", stuck)
            with pytest.raises(EpisodeError, match="passou de"):
                # This outer limit only keeps the test from hanging.
                await asyncio.wait_for(
                    service.generate_episode(scheduled=True, send=True), timeout=5
                )
            return telegram.sent

    sent = asyncio.run(scenario())

    assert [chat_id for chat_id, _ in sent] == ["11"]
    assert "<b>Etapa:</b> montagem do áudio" in sent[0][1]


def test_a_timeout_inside_the_run_keeps_its_own_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def times_out(*_args: object) -> EpisodeReport:
        raise TimeoutError("o ffmpeg demorou")

    async def scenario() -> None:
        async with httpx.AsyncClient() as client:
            service = telegram_service(client, FakeTelegram(client), "-22")
            monkeypatch.setattr(service, "_generate", times_out)
            await service.generate_episode(scheduled=True, send=False)

    with pytest.raises(TimeoutError, match="o ffmpeg demorou"):
        asyncio.run(scenario())


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


def test_without_the_gemini_key_the_run_fails_at_the_selection_at_once(
    monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    settings.GEMINI_API_KEY = None
    waits = record_waits(monkeypatch)
    item = NewsItem(
        id="1",
        outlet="g1",
        section="Política",
        title="t",
        summary="",
        link="",
        published_at=None,
    )

    async def one_item(*_args: object) -> list[NewsItem]:
        return [item]

    def no_model(*_args: object) -> BaseChatModel:
        raise AssertionError("no model should be built without its key")

    monkeypatch.setattr(service_module, "fetch_items", one_item)

    async def scenario() -> EpisodeService:
        async with httpx.AsyncClient() as client:
            service = EpisodeService(
                http_client=client,
                gemini=None,
                telegram=None,
                chat_id=None,
                settings=episode_settings(PodcastSettings()),
                sources=[],
                model_factory=no_model,
            )
            with pytest.raises(TextError, match="GEMINI_API_KEY não configurada"):
                await service.generate_episode(scheduled=False, send=False)
            return service

    service = asyncio.run(scenario())

    assert service.step == "seleção das notícias"
    assert waits == []

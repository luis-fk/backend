import asyncio
from collections.abc import Sequence
from pathlib import Path

import httpx
import pytest
from langchain_core.language_models import BaseChatModel
from pytest_django import Settings

from news_podcast.api.core.config import VOICE_RETRY_MINUTES
from news_podcast.api.core.llm import TextError
from news_podcast.api.core.schemas import Host, Script, Turn, Usage
from news_podcast.api.core.telegram import (
    TelegramClient,
    TelegramError,
)
from news_podcast.api.core.voice.base import VoiceError, VoiceUnavailableError
from news_podcast.api.episode import service as service_module
from news_podcast.api.episode.run import episode_settings
from news_podcast.api.episode.schemas import (
    EpisodeReport,
    NewsItem,
    SelectedStory,
    StoryBrief,
)
from news_podcast.api.episode.service import (
    EpisodeError,
    EpisodeService,
)
from news_podcast.models import PodcastSettings

TURNS = [Turn(speaker="Bia", text="Bom dia")]
ITEM = NewsItem(
    id="1",
    outlet="g1",
    section="Política",
    title="t",
    summary="",
    link="",
    published_at=None,
)
TEXT_USAGE = Usage(
    step="selection", model="gemini-3.8-flash", input_tokens=10, output_tokens=5
)


def record_waits(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    waits: list[float] = []

    async def record(seconds: float) -> None:
        waits.append(seconds)

    monkeypatch.setattr(asyncio, "sleep", record)
    return waits


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

    async def one_item(*_args: object) -> list[NewsItem]:
        return [ITEM]

    def no_model(*_args: object) -> BaseChatModel:
        raise AssertionError("no model should be built without its key")

    monkeypatch.setattr(service_module, "fetch_items", one_item)

    async def scenario() -> EpisodeService:
        async with httpx.AsyncClient() as client:
            service = EpisodeService(
                http_client=client,
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


def reach_the_voice(
    monkeypatch: pytest.MonkeyPatch, service: EpisodeService, tmp_path: Path
) -> None:
    """Fakes the steps before the voice: one headline, a selection that paid for an
    answer, no briefs and a script."""

    async def one_item(*_args: object) -> list[NewsItem]:
        return [ITEM]

    async def select(*_args: object) -> list[SelectedStory]:
        service.usages.append(TEXT_USAGE)
        return []

    async def no_briefs(*_args: object) -> list[StoryBrief]:
        return []

    async def write(*_args: object) -> Script:
        return Script(turns=TURNS)

    monkeypatch.setattr(service_module, "fetch_items", one_item)
    monkeypatch.setattr(service_module, "build_briefs", no_briefs)
    monkeypatch.setattr(service_module, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(service, "_select_stories", select)
    monkeypatch.setattr(service, "_write_script", write)


def no_voice_request(request: httpx.Request) -> httpx.Response:
    raise AssertionError("no voice request should be made")


def fail_at_the_voice(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, voice_model: str
) -> tuple[EpisodeService, list[tuple[str, str]], VoiceError]:
    async def scenario() -> tuple[EpisodeService, list[tuple[str, str]], VoiceError]:
        transport = httpx.MockTransport(no_voice_request)
        async with httpx.AsyncClient(transport=transport) as client:
            telegram = FakeTelegram(client)
            snapshot = episode_settings(PodcastSettings()).model_copy(
                update={"voice_model": voice_model}
            )
            service = EpisodeService(
                http_client=client,
                telegram=telegram,
                chat_id="-22",
                settings=snapshot,
                sources=[],
                admin_chat_id="11",
            )
            reach_the_voice(monkeypatch, service, tmp_path)
            with pytest.raises(VoiceError) as caught:
                await service.generate_episode(scheduled=False, send=True)
            return service, telegram.sent, caught.value

    return asyncio.run(scenario())


def test_a_voice_model_without_an_implementation_fails_at_the_voice_step(
    monkeypatch: pytest.MonkeyPatch, settings: Settings, tmp_path: Path
) -> None:
    settings.GEMINI_API_KEY = "test-key"

    service, sent, error = fail_at_the_voice(
        monkeypatch, tmp_path, "openai:gpt-4o-mini-tts"
    )

    assert "openai:gpt-4o-mini-tts" in str(error)
    assert service.step == "voz"
    assert service.usages == [TEXT_USAGE]
    assert [chat_id for chat_id, _ in sent] == ["11"]
    assert "<b>Etapa:</b> voz" in sent[0][1]
    assert "openai:gpt-4o-mini-tts" in sent[0][1]


def test_without_the_gemini_key_the_voice_step_fails_before_any_request(
    monkeypatch: pytest.MonkeyPatch, settings: Settings, tmp_path: Path
) -> None:
    settings.GEMINI_API_KEY = None

    service, sent, error = fail_at_the_voice(
        monkeypatch, tmp_path, "gemini-3.8-flash-lite-tts"
    )

    assert "GEMINI_API_KEY" in str(error)
    assert service.step == "voz"
    assert service.usages == [TEXT_USAGE]
    assert [chat_id for chat_id, _ in sent] == ["11"]
    assert "<b>Etapa:</b> voz" in sent[0][1]
    assert "GEMINI_API_KEY" in sent[0][1]


class FlakyVoice:
    """Unavailable once, then it answers."""

    def __init__(self, usage: Usage) -> None:
        self.usage = usage
        self.failures: list[Exception] = [VoiceUnavailableError("503")]

    async def synthesize(
        self,
        turns: list[Turn],
        hosts: Sequence[Host],
        *,
        style: str,
        headline_style: str,
        step: str,
    ) -> tuple[bytes, Usage]:
        if self.failures:
            raise self.failures.pop(0)
        return b"audio", self.usage


def test_the_voice_step_draws_on_the_run_s_waits_and_keeps_its_usage(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    waits = record_waits(monkeypatch)
    voice_usage = Usage(step="voice", model="gemini-3.8-flash-lite-tts")
    built: list[str] = []

    def provider(model: str, http_client: httpx.AsyncClient) -> FlakyVoice:
        built.append(model)
        return FlakyVoice(voice_usage)

    async def voice_note(*_args: object) -> float:
        return 60.0

    async def scenario() -> EpisodeService:
        transport = httpx.MockTransport(no_voice_request)
        async with httpx.AsyncClient(transport=transport) as client:
            service = EpisodeService(
                http_client=client,
                telegram=None,
                chat_id=None,
                settings=episode_settings(PodcastSettings()),
                sources=[],
            )
            reach_the_voice(monkeypatch, service, tmp_path)
            monkeypatch.setattr(service_module, "voice_provider", provider)
            monkeypatch.setattr(service_module, "build_voice_note", voice_note)
            await service.generate_episode(scheduled=False, send=False)
            return service

    service = asyncio.run(scenario())

    assert built == [service.settings.voice_model]
    assert waits == [VOICE_RETRY_MINUTES[0] * 60]
    assert service.voice_waits == list(VOICE_RETRY_MINUTES[1:])
    assert service.usages == [TEXT_USAGE, voice_usage]

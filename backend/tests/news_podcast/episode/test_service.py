import asyncio
import json
from collections.abc import Callable, Sequence
from datetime import datetime, time
from pathlib import Path
from typing import Any

import httpx
import pytest

from news_podcast.api.core import config as core_config
from news_podcast.api.core.gemini import (
    GeminiClient,
    GeminiError,
    GeminiQuotaExhaustedError,
    GeminiUnavailableError,
)
from news_podcast.api.core.schemas import (
    Host,
    Script,
    Turn,
    Usage,
)
from news_podcast.api.core.telegram import (
    TelegramClient,
    TelegramError,
)
from news_podcast.api.core.turns import (
    MIN_SCRIPT_TURNS,
)
from news_podcast.api.episode import config
from news_podcast.api.episode.run import episode_settings
from news_podcast.api.episode.schemas import (
    EpisodeReport,
    StorySelection,
)
from news_podcast.api.episode.service import (
    EpisodeError,
    EpisodeService,
)
from news_podcast.models import PodcastSettings

TURNS = [Turn(speaker="Bia", text="Bom dia")]


class FakeGemini(GeminiClient):
    """The text model is unavailable; the fallback answers `first_texts`, in order,
    and then `text`."""

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        voice_failures: list[Exception],
        text: str = '{"ok": true}',
        first_texts: Sequence[str] = (),
    ) -> None:
        super().__init__(http_client, "key")
        self.voice_failures = voice_failures
        self.text = text
        self.first_texts = list(first_texts)
        self.text_models: list[str] = []
        self.schemas: list[dict[str, Any]] = []

    async def generate_json(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        step: str,
        thinking_level: str | None = None,
        *,
        schema: dict[str, Any],
    ) -> tuple[dict[str, Any], Usage]:
        self.text_models.append(model)
        self.schemas.append(schema)
        if model == config.TEXT_MODEL:
            raise GeminiUnavailableError("Gemini respondeu 503: high demand")
        text = self.first_texts.pop(0) if self.first_texts else self.text
        answer = {"candidates": [{"content": {"parts": [{"text": text}]}}]}
        return answer, Usage(step=step, model=model)

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


def test_text_skips_the_main_model_once_it_is_unavailable() -> None:
    async def scenario() -> list[str]:
        async with httpx.AsyncClient() as client:
            gemini = FakeGemini(client, voice_failures=[])
            service = make_service(client, gemini)
            for step in ("selection", "script"):
                await service._ask_json(
                    "system", "user", step, StorySelection, lambda data: data
                )
            return gemini.text_models

    models = asyncio.run(scenario())

    assert models == [
        config.TEXT_MODEL,
        config.TEXT_FALLBACK_MODEL,
        config.TEXT_FALLBACK_MODEL,
    ]


def test_the_answer_follows_the_steps_schema_and_is_read_as_json() -> None:
    async def scenario() -> tuple[Any, list[dict[str, Any]]]:
        async with httpx.AsyncClient() as client:
            gemini = FakeGemini(client, voice_failures=[])
            service = make_service(client, gemini)
            answer = await service._ask_json(
                "system", "user", "selection", StorySelection, lambda data: data
            )
            return answer, gemini.schemas

    answer, schemas = asyncio.run(scenario())

    assert answer == {"ok": True}
    assert schemas == [StorySelection.model_json_schema(mode="serialization")] * 2


def test_gemini_must_fill_every_field_of_the_answer() -> None:
    story = StorySelection.model_json_schema(mode="serialization")["$defs"]
    turn = Script.model_json_schema(mode="serialization")["$defs"]

    assert story["SelectedStory"]["required"] == [
        "title",
        "category",
        "minutes",
        "angle",
        "item_ids",
    ]
    assert turn["Turn"]["required"] == ["speaker", "text", "headline"]


def test_a_broken_answer_is_asked_again_once() -> None:
    async def scenario() -> tuple[Any, list[str]]:
        async with httpx.AsyncClient() as client:
            gemini = FakeGemini(client, voice_failures=[], first_texts=['{"turns": ['])
            service = make_service(client, gemini)
            answer = await service._ask_json(
                "system", "user", "script", Script, lambda data: data
            )
            return answer, gemini.text_models

    answer, models = asyncio.run(scenario())

    assert answer == {"ok": True}
    assert models == [
        config.TEXT_MODEL,
        config.TEXT_FALLBACK_MODEL,
        config.TEXT_FALLBACK_MODEL,
    ]


def test_broken_answers_still_count_in_the_cost() -> None:
    async def scenario() -> list[Usage]:
        async with httpx.AsyncClient() as client:
            gemini = FakeGemini(client, voice_failures=[], text='{"turns": [')
            service = make_service(client, gemini)
            with pytest.raises(EpisodeError, match="JSON inválido"):
                await service._ask_each_model(
                    "system", "user", "script", Script, lambda data: data
                )
            return service.usages

    usages = asyncio.run(scenario())

    assert [usage.model for usage in usages] == [
        config.TEXT_FALLBACK_MODEL,
        config.TEXT_FALLBACK_MODEL,
    ]


MAIN = config.TEXT_MODEL
FALLBACK = config.TEXT_FALLBACK_MODEL
BUSY = GeminiUnavailableError("Gemini respondeu 503: high demand")
OUT_OF_QUOTA = GeminiQuotaExhaustedError("Gemini respondeu 429: quota")
ANSWER = '{"ok": true}'


class ScriptedGemini(FakeGemini):
    """Each text model answers, or fails, as its list in `outcomes` says, call by
    call."""

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        outcomes: dict[str, list[str | Exception]],
    ) -> None:
        super().__init__(http_client, voice_failures=[])
        self.outcomes = outcomes

    async def generate_json(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        step: str,
        thinking_level: str | None = None,
        *,
        schema: dict[str, Any],
    ) -> tuple[dict[str, Any], Usage]:
        self.text_models.append(model)
        if not self.outcomes[model]:
            raise AssertionError(f"{model} was asked more times than expected")
        outcome = self.outcomes[model].pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        answer = {"candidates": [{"content": {"parts": [{"text": outcome}]}}]}
        return answer, Usage(step=step, model=model)


def ask_scripted(
    outcomes: dict[str, list[str | Exception]],
    parse: Callable[[Any], Any] = lambda data: data,
) -> tuple[list[str], EpisodeError | None]:
    """Asks for one answer; returns the models asked, in order, and the error."""

    async def scenario() -> tuple[list[str], EpisodeError | None]:
        async with httpx.AsyncClient() as client:
            gemini = ScriptedGemini(client, outcomes)
            service = make_service(client, gemini)
            try:
                await service._ask_json(
                    "system", "user", "script", StorySelection, parse
                )
            except EpisodeError as error:
                return gemini.text_models, error
            return gemini.text_models, None

    return asyncio.run(scenario())


def test_text_waits_and_asks_every_model_again_when_none_answers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    waits = record_waits(monkeypatch)

    asked, error = ask_scripted({MAIN: [BUSY, BUSY], FALLBACK: [BUSY, ANSWER]})

    assert error is None
    assert waits == [core_config.TEXT_RETRY_MINUTES[0] * 60]
    assert asked == [MAIN, FALLBACK, MAIN, FALLBACK]


def test_text_gives_up_after_the_last_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    waits = record_waits(monkeypatch)
    rounds = len(core_config.TEXT_RETRY_MINUTES) + 1

    _, error = ask_scripted({MAIN: [BUSY] * rounds, FALLBACK: [BUSY] * rounds})

    assert error is not None
    assert waits == [minutes * 60 for minutes in core_config.TEXT_RETRY_MINUTES]


def test_the_text_waits_are_shared_by_the_whole_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    waits = record_waits(monkeypatch)

    async def scenario() -> EpisodeError | None:
        async with httpx.AsyncClient() as client:
            gemini = ScriptedGemini(
                client, {MAIN: [BUSY] * 3, FALLBACK: [BUSY, BUSY, ANSWER, BUSY]}
            )
            service = make_service(client, gemini)
            await service._ask_json(
                "system", "user", "selection", StorySelection, lambda data: data
            )
            try:
                await service._ask_json(
                    "system", "user", "script", StorySelection, lambda data: data
                )
            except EpisodeError as error:
                return error
            return None

    error = asyncio.run(scenario())

    assert error is not None
    assert waits == [minutes * 60 for minutes in core_config.TEXT_RETRY_MINUTES]


def test_text_does_not_wait_when_the_answers_are_bad(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    waits = record_waits(monkeypatch)

    def reject(_data: Any) -> Any:
        raise GeminiError("a seleção veio sem notícias válidas")

    asked, error = ask_scripted(
        {MAIN: [ANSWER, ANSWER], FALLBACK: [ANSWER, ANSWER]}, parse=reject
    )

    assert error is not None
    assert waits == []
    assert asked == [MAIN, MAIN, FALLBACK, FALLBACK]


def test_text_does_not_wait_when_the_daily_quota_is_over(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    waits = record_waits(monkeypatch)

    _, error = ask_scripted({MAIN: [OUT_OF_QUOTA], FALLBACK: [OUT_OF_QUOTA]})

    assert error is not None
    assert waits == []


def test_a_model_out_of_quota_is_not_asked_again_after_the_wait(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record_waits(monkeypatch)

    asked, error = ask_scripted({MAIN: [OUT_OF_QUOTA], FALLBACK: [BUSY, ANSWER]})

    assert error is None
    assert asked == [MAIN, FALLBACK, FALLBACK]


def test_lengthening_the_script_does_not_wait_for_the_models(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    waits = record_waits(monkeypatch)
    turn = {"speaker": "Bia", "text": "Bom dia", "headline": False}
    short_script = json.dumps({"turns": [turn] * MIN_SCRIPT_TURNS})
    start = datetime(2026, 11, 9, 6, 0, tzinfo=core_config.LOCAL_TZ)

    async def scenario() -> Script:
        async with httpx.AsyncClient() as client:
            gemini = ScriptedGemini(
                client,
                {MAIN: [BUSY] * 3, FALLBACK: [short_script, BUSY, BUSY, BUSY]},
            )
            service = make_service(client, gemini)
            return await service._write_script(
                [], start, start, start.date(), time(7, 0)
            )

    script = asyncio.run(scenario())

    assert len(script.turns) == MIN_SCRIPT_TURNS
    assert waits == []


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

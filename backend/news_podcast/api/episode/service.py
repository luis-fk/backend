import asyncio
import json
import logging
import tempfile
from collections.abc import Callable
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from news_podcast.api.core import config
from news_podcast.api.core.audio import build_voice_note
from news_podcast.api.core.gemini import (
    GeminiClient,
    GeminiError,
    GeminiQuotaExhaustedError,
    GeminiUnavailableError,
    answer_json,
)
from news_podcast.api.core.schemas import Script, Turn, Usage
from news_podcast.api.core.telegram import TelegramClient, notify_failure
from news_podcast.api.core.turns import chunk_turns, count_words
from news_podcast.api.episode.articles import build_briefs
from news_podcast.api.episode.config import (
    NEWS_CUTOFF_HOURS_BEFORE_SEND,
    NEWS_WINDOW_HOURS,
    SHORT_SCRIPT_RATIO,
)
from news_podcast.api.episode.feeds import fetch_items, format_for_selection
from news_podcast.api.episode.messages import (
    FAILURE_SUBJECT,
    episode_caption,
    episode_details,
)
from news_podcast.api.episode.options import (
    news_window,
    next_send,
    podcast_name,
    story_range,
    word_range,
    words_per_minute,
)
from news_podcast.api.episode.schemas import (
    EpisodeReport,
    EpisodeSettings,
    FeedSource,
    NewsItem,
    SelectedStory,
    StoryBrief,
    StorySelection,
)
from news_podcast.api.episode.script import (
    expand_prompt,
    format_briefs,
    parse_script,
    script_prompt,
)
from news_podcast.api.episode.selection import (
    log_selection,
    selection_prompt,
    valid_stories,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


# A failed answer, like invalid JSON, can be a one-off, so each model gets a second
# try before the next one.
ANSWERS_PER_MODEL = 2


class EpisodeError(Exception):
    pass


class EpisodeService:
    def __init__(
        self,
        http_client: httpx.AsyncClient,
        gemini: GeminiClient | None,
        telegram: TelegramClient | None,
        chat_id: str | None,
        settings: EpisodeSettings,
        sources: list[FeedSource],
        admin_chat_id: str | None = None,
    ) -> None:
        self.http_client = http_client
        self.gemini = gemini
        self.telegram = telegram
        self.chat_id = chat_id
        # Errors go here, not to the episode's chat.
        self.admin_chat_id = admin_chat_id or chat_id
        self.settings = settings
        # Read from the database by run.py, outside the event loop.
        self.sources = sources
        self.options = settings.options
        self.step = "início"
        # Every Gemini answer, kept as the run goes, so a failed run has its cost too.
        self.usages: list[Usage] = []
        # Text models that are down get asked again after a wait; the ones out of quota
        # don't.
        self.unavailable_models: set[str] = set()
        self.exhausted_models: set[str] = set()
        self.text_retry_minutes = list(config.TEXT_RETRY_MINUTES)
        self.voice_retry_minutes = list(config.VOICE_RETRY_MINUTES)

    async def generate_episode(self, *, scheduled: bool, send: bool) -> EpisodeReport:
        now = datetime.now(UTC)
        # The hour the episode is named after. It goes out as soon as it is ready:
        # the cron's start time sets when it arrives, and a process left waiting for
        # the hour could die with the episode in it.
        send_at = next_send(now, config.LOCAL_TZ)
        # A scheduled run reads the news up to the full hour before send_at, where
        # the previous day's window ended; a run without --scheduled reads up to now.
        scheduled_for = send_at if scheduled else None
        try:
            report = await self._make_and_send(now, send_at, scheduled_for, send)
        except Exception as error:
            logger.exception(f"Episode failed during '{self.step}'")
            if send:
                await notify_failure(
                    self.telegram, self.admin_chat_id, FAILURE_SUBJECT, self.step, error
                )
            raise
        return report

    async def _make_and_send(
        self,
        now: datetime,
        send_at: datetime,
        scheduled_for: datetime | None,
        send: bool,
    ) -> EpisodeReport:
        """Stops the run after MAX_RUN_MINUTES, at the await it is in. A call
        running in a thread, like trafilatura's, can't be stopped."""
        limit = asyncio.timeout(config.MAX_RUN_MINUTES * 60)
        try:
            async with limit:
                report = await self._generate(now, send_at, scheduled_for)
                if send:
                    self.step = "envio"
                    await self._deliver(report)
                return report
        except TimeoutError as error:
            if not limit.expired():
                raise
            raise EpisodeError(
                f"A execução passou de {config.MAX_RUN_MINUTES} minutos"
            ) from error

    async def _generate(
        self, now: datetime, send_at: datetime, scheduled_for: datetime | None
    ) -> EpisodeReport:
        day = (scheduled_for or now).astimezone(config.LOCAL_TZ).date()
        start, end = news_window(
            now,
            scheduled_for,
            NEWS_WINDOW_HOURS,
            NEWS_CUTOFF_HOURS_BEFORE_SEND,
        )
        logger.info(
            f"The {send_at:%H:%M} episode, of {self.options.min_minutes}-"
            f"{self.options.max_minutes} min at {self.options.speech_speed:g}x"
        )
        config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        self.step = "leitura dos feeds"
        items = await fetch_items(self.http_client, self.sources, start, end)
        logger.info(f"Collected {len(items)} items from {len(self.sources)} feeds")
        if not items:
            raise EpisodeError("Nenhuma notícia encontrada nos feeds")

        self.step = "seleção das notícias"
        stories = await self._select_stories(items, start, end)

        self.step = "leitura das matérias"
        briefs = await build_briefs(
            self.http_client, stories, {item.id: item for item in items}
        )

        self.step = "roteiro"
        script = await self._write_script(briefs, start, end, day, send_at.time())
        save_debug("script.json", script.model_dump())

        with tempfile.TemporaryDirectory(prefix="news_podcast_") as tmp:
            workdir = Path(tmp)
            self.step = "voz"
            parts = await self._narrate(script.turns, workdir)

            self.step = "montagem do áudio"
            audio_path = config.OUTPUT_DIR / f"resumo-{day:%Y-%m-%d}.ogg"
            duration = await build_voice_note(
                parts, audio_path, self.options.speech_speed, workdir
            )

        caption = episode_caption(podcast_name(send_at.time()), day)
        details = episode_details(
            briefs=briefs, usages=self.usages, prices=self.settings.prices
        )
        logger.info(f"Episode ready: {duration:.0f}s\n{caption}\n{details}")
        return EpisodeReport(
            audio_path=audio_path,
            duration_seconds=duration,
            caption=caption,
            script_words=count_words(script.turns),
        )

    async def _select_stories(
        self, items: list[NewsItem], start: datetime, end: datetime
    ) -> list[SelectedStory]:
        items_by_id = {item.id: item for item in items}
        system_prompt = selection_prompt(
            self.settings.selection_prompt, self.options, start, end
        )
        _, max_stories = story_range(self.options)

        def parse(data: Any) -> list[SelectedStory]:
            selection = StorySelection.model_validate(data)
            stories = valid_stories(selection, items_by_id, max_stories)
            if not stories:
                raise GeminiError("a seleção veio sem notícias válidas")
            return stories

        stories = await self._ask_json(
            system_prompt,
            format_for_selection(items, config.LOCAL_TZ),
            "selection",
            StorySelection,
            parse,
        )
        save_debug("selection.json", [story.model_dump() for story in stories])
        log_selection(stories, items_by_id)
        return stories

    async def _write_script(
        self,
        briefs: list[StoryBrief],
        start: datetime,
        end: datetime,
        day: date,
        send_at: time,
    ) -> Script:
        min_words, _ = word_range(self.options)
        system_prompt = script_prompt(
            self.settings.script_prompt, self.options, day, start, end, send_at
        )
        user_prompt = format_briefs(briefs, words_per_minute(self.options))
        script = await self._ask_json(
            system_prompt, user_prompt, "script", Script, parse_script
        )

        words = count_words(script.turns)
        logger.info(f"Script has {words} words in {len(script.turns)} turns")
        if words >= SHORT_SCRIPT_RATIO * min_words:
            return script

        expand = expand_prompt(self.settings.expand_prompt, self.options, script)
        try:
            # One round and no wait: the short script will do.
            longer = await self._ask_each_model(
                system_prompt,
                f"{user_prompt}\n\n{expand}",
                "script",
                Script,
                parse_script,
            )
        except EpisodeError as error:
            logger.warning(f"Could not lengthen the script: {error}")
            return script

        logger.info(f"Lengthened script has {count_words(longer.turns)} words")
        return longer if count_words(longer.turns) > words else script

    async def _ask_json(
        self,
        system_prompt: str,
        user_prompt: str,
        step: str,
        answer_model: type[BaseModel],
        parse: Callable[[Any], T],
    ) -> T:
        """When no text model answers well and one of them is marked down, waits
        TEXT_RETRY_MINUTES and asks them all again. The waits are shared by the whole
        run."""
        while True:
            try:
                return await self._ask_each_model(
                    system_prompt, user_prompt, step, answer_model, parse
                )
            except EpisodeError:
                # With no model down, bad answers and a used-up quota don't get better
                # with time.
                if not (self.unavailable_models and self.text_retry_minutes):
                    raise
            minutes = self.text_retry_minutes.pop(0)
            logger.warning(f"No text model answered; asking again in {minutes} min")
            await asyncio.sleep(minutes * 60)
            self.unavailable_models.clear()

    async def _ask_each_model(
        self,
        system_prompt: str,
        user_prompt: str,
        step: str,
        answer_model: type[BaseModel],
        parse: Callable[[Any], T],
    ) -> T:
        """One round: asks each available text model up to ANSWERS_PER_MODEL times."""
        gemini = self._require_gemini()
        # The serialization schema requires the fields that have defaults too
        # (json_schema_serialization_defaults_required), so Gemini writes them all.
        schema = answer_model.model_json_schema(mode="serialization")
        errors: list[str] = []
        attempts = [
            model
            for model in self._available_text_models()
            for _ in range(ANSWERS_PER_MODEL)
        ]

        for model in attempts:
            if model not in self._available_text_models():
                continue
            try:
                data, usage = await gemini.generate_json(
                    model,
                    system_prompt,
                    user_prompt,
                    step,
                    config.THINKING_LEVEL,
                    schema=schema,
                )
                self.usages.append(usage)
                result = parse(answer_json(data))
            except GeminiQuotaExhaustedError as error:
                self.exhausted_models.add(model)
                logger.warning(
                    f"{model} is out of quota, skipping it from now on: {error}"
                )
                errors.append(f"{model}: {error}")
                continue
            except GeminiUnavailableError as error:
                self.unavailable_models.add(model)
                logger.warning(f"{model} is unavailable, skipping it for now: {error}")
                errors.append(f"{model}: {error}")
                continue
            except (GeminiError, ValidationError) as error:
                logger.warning(f"{model} failed during {step}: {error}")
                errors.append(f"{model}: {error}")
                continue

            return result

        raise EpisodeError(" | ".join(errors) or "Nenhum modelo de texto disponível")

    def _available_text_models(self) -> list[str]:
        return [
            model
            for model in self.settings.text_models
            if model not in self.unavailable_models | self.exhausted_models
        ]

    async def _narrate(self, turns: list[Turn], workdir: Path) -> list[Path]:
        gemini = self._require_gemini()
        chunks = chunk_turns(turns, config.TTS_CHUNK_WORDS)
        parts: list[Path] = []
        for index, chunk in enumerate(chunks, start=1):
            logger.info(f"Gemini voice: part {index} of {len(chunks)}")
            audio, usage = await self._synthesize_patiently(gemini, chunk)
            self.usages.append(usage)
            path = workdir / f"gemini_{index:03d}.wav"
            path.write_bytes(audio)
            parts.append(path)
        return parts

    async def _synthesize_patiently(
        self, gemini: GeminiClient, turns: list[Turn]
    ) -> tuple[bytes, Usage]:
        while True:
            try:
                return await gemini.synthesize_dialogue(
                    self.settings.voice_model,
                    turns,
                    config.HOSTS,
                    "voice",
                    style=self.settings.voice_style,
                    headline_style=self.settings.headline_voice_style,
                )
            except GeminiQuotaExhaustedError:
                raise
            except GeminiUnavailableError as error:
                if not self.voice_retry_minutes:
                    raise
                minutes = self.voice_retry_minutes.pop(0)
                logger.warning(
                    f"Gemini voice is unavailable ({error}); "
                    f"trying again in {minutes} min"
                )
                await asyncio.sleep(minutes * 60)

    async def _deliver(self, report: EpisodeReport) -> None:
        telegram, chat_id = self._require_telegram()
        await telegram.send_voice(
            chat_id, report.audio_path, report.caption, round(report.duration_seconds)
        )

    def _require_gemini(self) -> GeminiClient:
        if self.gemini is None:
            raise EpisodeError("GEMINI_API_KEY não configurada")
        return self.gemini

    def _require_telegram(self) -> tuple[TelegramClient, str]:
        if self.telegram is None or not self.chat_id:
            raise EpisodeError("TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID não configurado")
        return self.telegram, self.chat_id


def save_debug(name: str, payload: Any) -> None:
    path = config.OUTPUT_DIR / name
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str))

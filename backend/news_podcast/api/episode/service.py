import asyncio
import json
import logging
import tempfile
from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, TypeVar

import httpx
from pydantic import ValidationError

from news_podcast.api.episode import config
from news_podcast.api.episode.articles import build_briefs
from news_podcast.api.episode.audio import build_voice_note
from news_podcast.api.episode.feeds import (
    fetch_items,
    format_for_selection,
    load_sources,
)
from news_podcast.api.episode.gemini import (
    GeminiClient,
    GeminiError,
    GeminiQuotaExhaustedError,
    GeminiUnavailableError,
)
from news_podcast.api.episode.messages import (
    episode_caption,
    episode_details,
    failure_message,
    long_date,
)
from news_podcast.api.episode.prompts import (
    EXPAND_PROMPT,
    SCRIPT_PROMPT,
    SELECTION_PROMPT,
)
from news_podcast.api.episode.schemas import (
    EpisodeReport,
    NewsItem,
    Script,
    SelectedStory,
    StoryBrief,
    StorySelection,
    Turn,
    Usage,
)
from news_podcast.api.episode.telegram import TelegramClient, TelegramError
from news_podcast.api.episode.utils import (
    chunk_turns,
    clean_turns,
    count_words,
    format_briefs,
    news_window,
    valid_stories,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")
MIN_SCRIPT_TURNS = 10


class EpisodeError(Exception):
    pass


class NewsPodcastService:
    def __init__(
        self,
        http_client: httpx.AsyncClient,
        gemini: GeminiClient | None,
        telegram: TelegramClient | None,
        chat_id: str | None,
    ) -> None:
        self.http_client = http_client
        self.gemini = gemini
        self.telegram = telegram
        self.chat_id = chat_id
        self.step = "início"
        self.unavailable_models: set[str] = set()
        self.voice_retry_minutes = list(config.VOICE_RETRY_MINUTES)

    async def generate_episode(self, *, scheduled: bool, send: bool) -> EpisodeReport:
        now = datetime.now(config.LOCAL_TZ)
        send_at = datetime.combine(now.date(), config.SEND_AT, tzinfo=config.LOCAL_TZ)
        try:
            report = await self._generate(now, scheduled)
        except Exception as error:
            logger.exception(f"Episode failed during '{self.step}'")
            if send:
                await notify_failure(self.telegram, self.chat_id, self.step, error)
            raise

        if send:
            if scheduled:
                await wait_until(send_at)
            await self._deliver(report)
        return report

    async def _generate(self, now: datetime, scheduled: bool) -> EpisodeReport:
        day = now.date()
        cutoff = config.NEWS_CUTOFF if scheduled else None
        start, end = news_window(now, cutoff, config.NEWS_WINDOW_HOURS)
        config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        self.step = "leitura dos feeds"
        sources = load_sources(config.OPML_PATH)
        items = await fetch_items(self.http_client, sources, start, end)
        logger.info(f"Collected {len(items)} items from {len(sources)} feeds")
        if not items:
            raise EpisodeError("Nenhuma notícia encontrada nos feeds")

        self.step = "seleção das notícias"
        stories, usages = await self._select_stories(items, start, end)

        self.step = "leitura das matérias"
        briefs = await build_briefs(
            self.http_client, stories, {item.id: item for item in items}
        )

        self.step = "roteiro"
        script, script_usages = await self._write_script(briefs, start, end, day)
        usages.extend(script_usages)
        save_debug("script.json", script.model_dump())

        with tempfile.TemporaryDirectory(prefix="news_podcast_") as tmp:
            workdir = Path(tmp)
            self.step = "voz"
            parts, voice_usages = await self._narrate(script.turns, workdir)
            usages.extend(voice_usages)

            self.step = "montagem do áudio"
            audio_path = config.OUTPUT_DIR / f"resumo-{day:%Y-%m-%d}.ogg"
            duration = await build_voice_note(parts, audio_path, workdir)

        caption = episode_caption(day)
        details = episode_details(day=day, briefs=briefs, usages=usages)
        logger.info(f"Episode ready: {duration:.0f}s\n{caption}\n{details}")
        return EpisodeReport(
            audio_path=audio_path, duration_seconds=duration, caption=caption
        )

    async def _select_stories(
        self, items: list[NewsItem], start: datetime, end: datetime
    ) -> tuple[list[SelectedStory], list[Usage]]:
        items_by_id = {item.id: item for item in items}

        def parse(data: Any) -> list[SelectedStory]:
            selection = StorySelection.model_validate(data)
            stories = valid_stories(selection, items_by_id, config.MAX_STORIES)
            if not stories:
                raise GeminiError("a seleção veio sem notícias válidas")
            return stories

        stories, usages = await self._ask_json(
            selection_prompt(start, end),
            format_for_selection(items, config.LOCAL_TZ),
            "selection",
            parse,
        )
        save_debug("selection.json", [story.model_dump() for story in stories])
        log_selection(stories, items_by_id)
        return stories, usages

    async def _write_script(
        self, briefs: list[StoryBrief], start: datetime, end: datetime, day: date
    ) -> tuple[Script, list[Usage]]:
        system_prompt = script_prompt(day, start, end)
        user_prompt = format_briefs(briefs, config.WORDS_PER_MINUTE)
        script, usages = await self._ask_json(
            system_prompt, user_prompt, "script", parse_script
        )

        words = count_words(script.turns)
        logger.info(f"Script has {words} words in {len(script.turns)} turns")
        if words >= config.SHORT_SCRIPT_RATIO * config.MIN_WORDS:
            return script, usages

        expand_prompt = EXPAND_PROMPT.format(
            words=words,
            min_words=config.MIN_WORDS,
            max_words=config.MAX_WORDS,
            script=script.model_dump_json(),
        )
        try:
            longer, more_usages = await self._ask_json(
                system_prompt,
                f"{user_prompt}\n\n{expand_prompt}",
                "script",
                parse_script,
            )
        except EpisodeError as error:
            logger.warning(f"Could not lengthen the script: {error}")
            return script, usages

        usages.extend(more_usages)
        logger.info(f"Lengthened script has {count_words(longer.turns)} words")
        return (longer if count_words(longer.turns) > words else script), usages

    async def _ask_json(
        self,
        system_prompt: str,
        user_prompt: str,
        step: str,
        parse: Callable[[Any], T],
    ) -> tuple[T, list[Usage]]:
        gemini = self._require_gemini()
        usages: list[Usage] = []
        errors: list[str] = []

        for model in self._available_text_models():
            try:
                data, usage = await gemini.generate_json(
                    model, system_prompt, user_prompt, step, config.THINKING_LEVEL
                )
                usages.append(usage)
                result = parse(data)
            except GeminiUnavailableError as error:
                self.unavailable_models.add(model)
                logger.warning(
                    f"{model} is unavailable, skipping it from now on: {error}"
                )
                errors.append(f"{model}: {error}")
                continue
            except (GeminiError, ValidationError) as error:
                logger.warning(f"{model} failed during {step}: {error}")
                errors.append(f"{model}: {error}")
                continue

            return result, usages

        raise EpisodeError(" | ".join(errors) or "Nenhum modelo de texto disponível")

    def _available_text_models(self) -> list[str]:
        return [
            model
            for model in (config.TEXT_MODEL, config.TEXT_FALLBACK_MODEL)
            if model not in self.unavailable_models
        ]

    async def _narrate(
        self, turns: list[Turn], workdir: Path
    ) -> tuple[list[Path], list[Usage]]:
        gemini = self._require_gemini()
        chunks = chunk_turns(turns, config.TTS_CHUNK_WORDS)
        parts: list[Path] = []
        usages: list[Usage] = []
        for index, chunk in enumerate(chunks, start=1):
            logger.info(f"Gemini voice: part {index} of {len(chunks)}")
            audio, usage = await self._synthesize_patiently(gemini, chunk)
            usages.append(usage)
            path = workdir / f"gemini_{index:03d}.wav"
            path.write_bytes(audio)
            parts.append(path)
        return parts, usages

    async def _synthesize_patiently(
        self, gemini: GeminiClient, turns: list[Turn]
    ) -> tuple[bytes, Usage]:
        while True:
            try:
                return await gemini.synthesize_dialogue(
                    config.TTS_MODEL, turns, config.HOSTS, "voice"
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


async def notify_failure(
    telegram: TelegramClient | None, chat_id: str | None, step: str, error: Exception
) -> None:
    if telegram is None or not chat_id:
        return
    try:
        await telegram.send_message(chat_id, failure_message(step, error))
    except TelegramError as notify_error:
        logger.error(f"Could not report the failure on Telegram: {notify_error}")


def parse_script(data: Any) -> Script:
    script = Script.model_validate(data)
    turns = clean_turns(script.turns, config.HOSTS)
    if len(turns) < MIN_SCRIPT_TURNS:
        raise GeminiError(f"o roteiro veio com só {len(turns)} falas")
    return script.model_copy(update={"turns": turns})


async def wait_until(moment: datetime) -> None:
    delay = (moment - datetime.now(UTC)).total_seconds()
    if 0 < delay <= config.MAX_WAIT_SECONDS:
        local_moment = moment.astimezone(config.LOCAL_TZ)
        logger.info(f"Waiting {delay / 60:.0f} min to send at {local_moment:%H:%M}")
        await asyncio.sleep(delay)


def selection_prompt(start: datetime, end: datetime) -> str:
    return SELECTION_PROMPT.format(
        min_minutes=config.MIN_MINUTES,
        max_minutes=config.MAX_MINUTES,
        target_minutes=round((config.MIN_MINUTES + config.MAX_MINUTES) / 2),
        min_stories=config.MIN_STORIES,
        max_stories=config.MAX_STORIES,
        window_start=local_label(start),
        window_end=local_label(end),
    )


def script_prompt(day: date, start: datetime, end: datetime) -> str:
    return SCRIPT_PROMPT.format(
        podcast_name=config.PODCAST_NAME,
        host_a=config.HOSTS[0].name,
        host_b=config.HOSTS[1].name,
        today=long_date(day),
        window_start=local_label(start),
        window_end=local_label(end),
        min_words=config.MIN_WORDS,
        max_words=config.MAX_WORDS,
    )


def local_label(moment: datetime) -> str:
    return moment.astimezone(config.LOCAL_TZ).strftime("%d/%m às %H:%M")


def save_debug(name: str, payload: Any) -> None:
    path = config.OUTPUT_DIR / name
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


def log_selection(
    stories: Sequence[SelectedStory], items_by_id: dict[str, NewsItem]
) -> None:
    for story in stories:
        outlets = sorted({items_by_id[item_id].outlet for item_id in story.item_ids})
        logger.info(
            f"Story ({story.minutes} min): {story.title} | {', '.join(outlets)}"
        )

    has_preferred = any(
        items_by_id[item_id].outlet in config.PREFERRED_OUTLETS
        for story in stories
        for item_id in story.item_ids
    )
    if not has_preferred:
        logger.info("No story from the preferred outlets today")

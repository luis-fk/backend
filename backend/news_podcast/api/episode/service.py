import asyncio
import json
import logging
import tempfile
from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

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
    answer_json,
)
from news_podcast.api.episode.messages import (
    chat_id_message,
    chat_list_message,
    episode_caption,
    episode_details,
    failure_message,
    long_date,
)
from news_podcast.api.episode.options import (
    greeting,
    next_send,
    podcast_name,
    spoken_time,
    story_range,
    target_minutes,
    word_range,
    words_per_minute,
)
from news_podcast.api.episode.schemas import (
    EpisodeOptions,
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
from news_podcast.models import PodcastSettings

logger = logging.getLogger(__name__)

T = TypeVar("T")
MIN_SCRIPT_TURNS = 10
# A failed answer, like invalid JSON, can be a one-off, so each model gets a second
# try before the next one.
ANSWERS_PER_MODEL = 2


class EpisodeError(Exception):
    pass


class NewsPodcastService:
    def __init__(
        self,
        http_client: httpx.AsyncClient,
        gemini: GeminiClient | None,
        telegram: TelegramClient | None,
        chat_id: str | None,
        podcast_settings: PodcastSettings,
        admin_chat_id: str | None = None,
    ) -> None:
        self.http_client = http_client
        self.gemini = gemini
        self.telegram = telegram
        self.chat_id = chat_id
        # Errors go here, not to the episode's chat.
        self.admin_chat_id = admin_chat_id or chat_id
        self.podcast_settings = podcast_settings
        self.options = podcast_settings.episode_options()
        self.step = "início"
        # Every Gemini answer, kept as the run goes, so a failed run has its cost too.
        self.usages: list[Usage] = []
        self.unavailable_models: set[str] = set()
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
            report = await self._generate(now, send_at, scheduled_for)
            if send:
                self.step = "envio"
                await self._deliver(report)
        except Exception as error:
            logger.exception(f"Episode failed during '{self.step}'")
            if send:
                await notify_failure(
                    self.telegram, self.admin_chat_id, self.step, error
                )
            raise
        return report

    async def _generate(
        self, now: datetime, send_at: datetime, scheduled_for: datetime | None
    ) -> EpisodeReport:
        day = (scheduled_for or now).astimezone(config.LOCAL_TZ).date()
        start, end = news_window(
            now,
            scheduled_for,
            config.NEWS_WINDOW_HOURS,
            config.NEWS_CUTOFF_HOURS_BEFORE_SEND,
        )
        logger.info(
            f"The {send_at:%H:%M} episode, of {self.options.min_minutes}-"
            f"{self.options.max_minutes} min at {self.options.speech_speed:g}x"
        )
        config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        self.step = "leitura dos feeds"
        sources = load_sources(config.OPML_PATH)
        items = await fetch_items(self.http_client, sources, start, end)
        logger.info(f"Collected {len(items)} items from {len(sources)} feeds")
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
            briefs=briefs, usages=self.usages, prices=self.podcast_settings.prices()
        )
        logger.info(f"Episode ready: {duration:.0f}s\n{caption}\n{details}")
        return EpisodeReport(
            audio_path=audio_path, duration_seconds=duration, caption=caption
        )

    async def _select_stories(
        self, items: list[NewsItem], start: datetime, end: datetime
    ) -> list[SelectedStory]:
        items_by_id = {item.id: item for item in items}
        system_prompt = selection_prompt(
            self.podcast_settings.selection_prompt, self.options, start, end
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
            self.podcast_settings.script_prompt, self.options, day, start, end, send_at
        )
        user_prompt = format_briefs(briefs, words_per_minute(self.options))
        script = await self._ask_json(
            system_prompt, user_prompt, "script", Script, parse_script
        )

        words = count_words(script.turns)
        logger.info(f"Script has {words} words in {len(script.turns)} turns")
        if words >= config.SHORT_SCRIPT_RATIO * min_words:
            return script

        expand = expand_prompt(
            self.podcast_settings.expand_prompt, self.options, script
        )
        try:
            longer = await self._ask_json(
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
            if model in self.unavailable_models:
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

            return result

        raise EpisodeError(" | ".join(errors) or "Nenhum modelo de texto disponível")

    def _available_text_models(self) -> list[str]:
        return [
            model
            for model in self.podcast_settings.text_models()
            if model not in self.unavailable_models
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
                    self.podcast_settings.voice_model,
                    turns,
                    config.HOSTS,
                    "voice",
                    style=self.podcast_settings.voice_style,
                    headline_style=self.podcast_settings.headline_voice_style,
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


async def send_chat_ids(
    telegram: TelegramClient | None, admin_chat_id: str | None
) -> int:
    """Sends the list of the chats the bot saw to the admin chat. On the first setup,
    with no chat configured, sends each chat its own id instead."""
    if telegram is None:
        raise EpisodeError("TELEGRAM_BOT_TOKEN não configurado")

    chats = await telegram.recent_chats()
    if not chats:
        raise EpisodeError(
            "Nenhuma conversa encontrada. Mande /start para o bot ou adicione ele "
            "a um grupo no Telegram e rode de novo."
        )
    if admin_chat_id:
        await telegram.send_message(admin_chat_id, chat_list_message(chats))
        return len(chats)

    for chat in chats:
        await telegram.send_message(chat.id, chat_id_message(chat.id))
    return len(chats)


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


# Each prompt gets the placeholders listed for it in prompts.py, the only ones the
# admin accepts.


def selection_prompt(
    template: str, options: EpisodeOptions, start: datetime, end: datetime
) -> str:
    min_stories, max_stories = story_range(options)
    return template.format(
        min_minutes=options.min_minutes,
        max_minutes=options.max_minutes,
        target_minutes=round(target_minutes(options)),
        min_stories=min_stories,
        max_stories=max_stories,
        window_start=local_label(start),
        window_end=local_label(end),
    )


def script_prompt(
    template: str,
    options: EpisodeOptions,
    day: date,
    start: datetime,
    end: datetime,
    send_at: time,
) -> str:
    min_words, max_words = word_range(options)
    return template.format(
        podcast_name=podcast_name(send_at),
        host_a=config.HOSTS[0].name,
        host_b=config.HOSTS[1].name,
        send_time=spoken_time(send_at),
        greeting=greeting(send_at),
        today=long_date(day),
        window_start=local_label(start),
        window_end=local_label(end),
        min_words=min_words,
        max_words=max_words,
    )


def expand_prompt(template: str, options: EpisodeOptions, script: Script) -> str:
    min_words, max_words = word_range(options)
    return template.format(
        words=count_words(script.turns),
        min_words=min_words,
        max_words=max_words,
        script=script.model_dump_json(),
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

import asyncio
import json
import logging
import tempfile
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import Any

import httpx

from news_podcast.api.core.audio import build_voice_note
from news_podcast.api.core.config import (
    LOCAL_TZ,
    MAX_RUN_MINUTES,
    OUTPUT_DIR,
    VOICE_RETRY_MINUTES,
)
from news_podcast.api.core.llm import ModelFactory, TextModels, chat_model
from news_podcast.api.core.schemas import Script, Usage
from news_podcast.api.core.telegram import TelegramClient, notify_failure
from news_podcast.api.core.turns import count_words
from news_podcast.api.core.voice.narration import narrate
from news_podcast.api.core.voice.providers import voice_provider
from news_podcast.api.episode.articles import build_briefs
from news_podcast.api.episode.config import (
    NEWS_CUTOFF_HOURS_BEFORE_SEND,
    NEWS_WINDOW_HOURS,
)
from news_podcast.api.episode.feeds import fetch_items
from news_podcast.api.episode.messages import (
    FAILURE_SUBJECT,
    episode_caption,
    episode_details,
)
from news_podcast.api.episode.options import (
    news_window,
    next_send,
    podcast_name,
)
from news_podcast.api.episode.schemas import (
    EpisodeReport,
    EpisodeSettings,
    FeedSource,
    NewsItem,
    SelectedStory,
    StoryBrief,
)
from news_podcast.api.episode.script import write_script
from news_podcast.api.episode.selection import select_stories

logger = logging.getLogger(__name__)


class EpisodeError(Exception):
    pass


class EpisodeService:
    def __init__(
        self,
        http_client: httpx.AsyncClient,
        telegram: TelegramClient | None,
        chat_id: str | None,
        settings: EpisodeSettings,
        sources: list[FeedSource],
        admin_chat_id: str | None = None,
        model_factory: ModelFactory = chat_model,
    ) -> None:
        self.http_client = http_client
        self.telegram = telegram
        self.chat_id = chat_id
        # Errors go here, not to the episode's chat.
        self.admin_chat_id = admin_chat_id or chat_id
        self.settings = settings
        # Read from the database by run.py, outside the event loop.
        self.sources = sources
        self.options = settings.options
        self.step = "início"
        # Every answer, kept as the run goes, so a failed run has its cost too.
        self.usages: list[Usage] = []
        # Built inside the run, so its waits and model marks are this run's.
        self.text = TextModels(
            settings.text_models, self.usages, http_client, model_factory
        )
        self.voice_waits = list(VOICE_RETRY_MINUTES)

    async def generate_episode(self, *, scheduled: bool, send: bool) -> EpisodeReport:
        now = datetime.now(UTC)
        # The hour the episode is named after. It goes out as soon as it is ready:
        # the cron's start time sets when it arrives, and a process left waiting for
        # the hour could die with the episode in it.
        send_at = next_send(now, LOCAL_TZ)
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
        limit = asyncio.timeout(MAX_RUN_MINUTES * 60)
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
                f"A execução passou de {MAX_RUN_MINUTES} minutos"
            ) from error

    async def _generate(
        self, now: datetime, send_at: datetime, scheduled_for: datetime | None
    ) -> EpisodeReport:
        day = (scheduled_for or now).astimezone(LOCAL_TZ).date()
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
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

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
            # Built here, so a voice model with no implementation or a missing key
            # fails this step, with its notice and its history row.
            parts = await narrate(
                voice_provider(self.settings.voice_model, self.http_client),
                script.turns,
                style=self.settings.voice_style,
                headline_style=self.settings.headline_voice_style,
                workdir=workdir,
                usages=self.usages,
                waits=self.voice_waits,
            )

            self.step = "montagem do áudio"
            audio_path = OUTPUT_DIR / f"resumo-{day:%Y-%m-%d}.ogg"
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
        stories = await select_stories(self.text, self.settings, items, start, end)
        save_debug("selection.json", [story.model_dump() for story in stories])
        return stories

    async def _write_script(
        self,
        briefs: list[StoryBrief],
        start: datetime,
        end: datetime,
        day: date,
        send_at: time,
    ) -> Script:
        return await write_script(
            self.text, self.settings, briefs, day, start, end, send_at
        )

    async def _deliver(self, report: EpisodeReport) -> None:
        telegram, chat_id = self._require_telegram()
        await telegram.send_voice(
            chat_id, report.audio_path, report.caption, round(report.duration_seconds)
        )

    def _require_telegram(self) -> tuple[TelegramClient, str]:
        if self.telegram is None or not self.chat_id:
            raise EpisodeError("TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID não configurado")
        return self.telegram, self.chat_id


def save_debug(name: str, payload: Any) -> None:
    path = OUTPUT_DIR / name
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str))

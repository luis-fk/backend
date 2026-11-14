import asyncio
import logging
from datetime import UTC, datetime
from typing import NamedTuple

import httpx
from django.db import DatabaseError, close_old_connections
from django.utils import timezone

from news_podcast.api.core.costs import total_cost_usd
from news_podcast.api.core.llm import ModelFactory, TextModels, chat_model
from news_podcast.api.core.schemas import NewsStory, Usage
from news_podcast.api.core.telegram import (
    admin_chat_id,
    chat_id,
    report_failure,
    telegram_client,
)
from news_podcast.api.episode.config import (
    NEWS_CUTOFF_HOURS_BEFORE_SEND,
    NEWS_WINDOW_HOURS,
)
from news_podcast.api.episode.feeds import fetch_items
from news_podcast.api.episode.messages import FAILURE_SUBJECT
from news_podcast.api.episode.options import news_window
from news_podcast.api.episode.schemas import EpisodeReport, EpisodeSettings, FeedSource
from news_podcast.api.episode.selection import select_stories
from news_podcast.api.episode.service import EpisodeError, EpisodeService
from news_podcast.models import Episode, Feed, PodcastSettings, SettingsMissing

logger = logging.getLogger(__name__)


class Run(NamedTuple):
    """What a run left for the history: the report or the error, the step it was
    in and the answers it paid for, text and voice."""

    report: EpisodeReport | None
    error: Exception | None
    step: str
    usages: list[Usage]


class Selection(NamedTuple):
    """The day's stories, the answers paid for and the error, if any."""

    stories: list[NewsStory]
    usages: list[Usage]
    error: Exception | None


def episode_settings(podcast_settings: PodcastSettings) -> EpisodeSettings:
    return EpisodeSettings(
        options=podcast_settings.episode_options(),
        text_models=tuple(podcast_settings.text_models()),
        voice_model=podcast_settings.voice_model,
        selection_prompt=podcast_settings.selection_prompt,
        script_prompt=podcast_settings.script_prompt,
        expand_prompt=podcast_settings.expand_prompt,
        voice_style=podcast_settings.voice_style,
        headline_voice_style=podcast_settings.headline_voice_style,
        prices=podcast_settings.prices(),
    )


def make_episode(*, scheduled: bool, send: bool) -> None:
    """Makes the episode with the settings from the admin and saves the run in the
    history, failed or not. The database is only used here, outside the event loop,
    where Django's ORM can run."""
    try:
        podcast_settings = PodcastSettings.load()
        sources = Feed.sources()
    except (DatabaseError, SettingsMissing) as error:
        if send:
            asyncio.run(report_failure(FAILURE_SUBJECT, "configurações", error))
        raise
    if scheduled and podcast_settings.paused:
        logger.info("The podcast is paused in the admin, so there is no episode")
        return

    snapshot = episode_settings(podcast_settings)
    started_at = timezone.now()
    run = asyncio.run(generate(snapshot, sources, scheduled=scheduled, send=send))
    if run.error:
        status = Episode.Status.FAILED
    else:
        status = Episode.Status.SENT if send else Episode.Status.NOT_SENT
    # A run can last up to MAX_RUN_MINUTES (2 hours), and Django only renews
    # connections between requests: this drops the one that read the settings, which
    # the database may have closed meanwhile, so the write opens a new one.
    close_old_connections()
    Episode.objects.create(
        started_at=started_at,
        status=status,
        duration_seconds=run.report.duration_seconds if run.report else None,
        script_words=run.report.script_words if run.report else None,
        cost_usd=total_cost_usd(run.usages, snapshot.prices),
        usage=[usage.model_dump() for usage in run.usages],
        error=f"{run.step}: {run.error}" if run.error else "",
    )
    if run.error:
        raise run.error


async def generate(
    snapshot: EpisodeSettings,
    sources: list[FeedSource],
    *,
    scheduled: bool,
    send: bool,
) -> Run:
    async with httpx.AsyncClient() as http_client:
        service = EpisodeService(
            http_client=http_client,
            telegram=telegram_client(http_client),
            chat_id=chat_id(),
            settings=snapshot,
            sources=sources,
            admin_chat_id=admin_chat_id(),
        )
        try:
            report = await service.generate_episode(scheduled=scheduled, send=send)
        except Exception as error:
            return Run(None, error, service.step, service.usages)
        return Run(report, None, service.step, service.usages)


def select_today(*, model_factory: ModelFactory = chat_model) -> Selection:
    """The day's stories, from the feeds and the selection only, with no episode and
    nothing sent. It never raises: a failure comes back with no stories, the answers
    already paid for and the error."""
    usages: list[Usage] = []
    try:
        snapshot = episode_settings(PodcastSettings.load())
        sources = Feed.sources()
        stories = asyncio.run(select(snapshot, sources, usages, model_factory))
    except Exception as error:
        logger.warning(f"The day's selection failed: {error}")
        return Selection([], usages, error)
    return Selection(stories, usages, None)


async def select(
    snapshot: EpisodeSettings,
    sources: list[FeedSource],
    usages: list[Usage],
    model_factory: ModelFactory,
) -> list[NewsStory]:
    start, end = news_window(
        datetime.now(UTC), None, NEWS_WINDOW_HOURS, NEWS_CUTOFF_HOURS_BEFORE_SEND
    )
    async with httpx.AsyncClient() as http_client:
        text = TextModels(snapshot.text_models, usages, http_client, model_factory)
        items = await fetch_items(http_client, sources, start, end)
        if not items:
            raise EpisodeError("Nenhuma notícia encontrada nos feeds")
        stories = await select_stories(text, snapshot, items, start, end)
    return [NewsStory(story.title, story.category, story.angle) for story in stories]

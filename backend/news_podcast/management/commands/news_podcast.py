import asyncio
import logging
from typing import Any, NamedTuple

import httpx
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import DatabaseError, close_old_connections
from django.utils import timezone

from news_podcast.api.episode.costs import total_cost_usd
from news_podcast.api.episode.gemini import GeminiClient
from news_podcast.api.episode.schemas import EpisodeReport, Usage
from news_podcast.api.episode.service import (
    NewsPodcastService,
    notify_failure,
    send_chat_ids,
)
from news_podcast.api.episode.telegram import TelegramClient
from news_podcast.models import Episode, PodcastSettings

ACTIONS = ("episode", "chat-id")
QUIET_LOGGERS = ("httpx", "httpcore", "trafilatura", "htmldate", "charset_normalizer")

logger = logging.getLogger(__name__)


class Run(NamedTuple):
    """What a run left for the history: the report or the error, the step it was
    in and the Gemini answers it paid for."""

    report: EpisodeReport | None
    error: Exception | None
    step: str
    usages: list[Usage]


class Command(BaseCommand):
    help = "Gera o resumo diário de notícias em áudio e envia no Telegram."
    requires_system_checks: list[str] = []

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("action", nargs="?", default="episode", choices=ACTIONS)
        parser.add_argument("--scheduled", action="store_true")
        parser.add_argument("--no-send", action="store_true")

    def handle(self, *args: Any, **options: Any) -> None:
        configure_logging()
        try:
            if options["action"] == "chat-id":
                asyncio.run(report_chat_ids())
            else:
                make_episode(
                    scheduled=options["scheduled"], send=not options["no_send"]
                )
        except Exception as error:
            raise CommandError(str(error)) from error


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    for name in QUIET_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)


def chat_id() -> str | None:
    return getattr(settings, "TELEGRAM_CHAT_ID", None) or None


def admin_chat_id() -> str | None:
    return getattr(settings, "TELEGRAM_ADMIN_CHAT_ID", None) or chat_id()


def telegram_client(http_client: httpx.AsyncClient) -> TelegramClient | None:
    bot_token = getattr(settings, "TELEGRAM_BOT_TOKEN", None)
    return TelegramClient(http_client, bot_token) if bot_token else None


def make_episode(*, scheduled: bool, send: bool) -> None:
    """Makes the episode with the settings from the admin and saves the run in the
    history, failed or not. The database is only used here, outside the event loop,
    where Django's ORM can run."""
    try:
        podcast_settings = PodcastSettings.load()
    except DatabaseError as error:
        if send:
            asyncio.run(report_failure("configurações", error))
        raise
    if scheduled and podcast_settings.paused:
        logger.info("The podcast is paused in the admin, so there is no episode")
        return

    started_at = timezone.now()
    run = asyncio.run(generate(podcast_settings, scheduled=scheduled, send=send))
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
        cost_usd=total_cost_usd(run.usages, podcast_settings.prices()),
        usage=[usage.model_dump() for usage in run.usages],
        error=f"{run.step}: {run.error}" if run.error else "",
    )
    if run.error:
        raise run.error


async def generate(
    podcast_settings: PodcastSettings, *, scheduled: bool, send: bool
) -> Run:
    api_key = getattr(settings, "GEMINI_API_KEY", None)
    async with httpx.AsyncClient() as http_client:
        service = NewsPodcastService(
            http_client=http_client,
            gemini=GeminiClient(http_client, api_key) if api_key else None,
            telegram=telegram_client(http_client),
            chat_id=chat_id(),
            podcast_settings=podcast_settings,
            admin_chat_id=admin_chat_id(),
        )
        try:
            report = await service.generate_episode(scheduled=scheduled, send=send)
        except Exception as error:
            return Run(None, error, service.step, service.usages)
        return Run(report, None, service.step, service.usages)


async def report_failure(step: str, error: Exception) -> None:
    async with httpx.AsyncClient() as http_client:
        await notify_failure(telegram_client(http_client), admin_chat_id(), step, error)


async def report_chat_ids() -> None:
    async with httpx.AsyncClient() as http_client:
        found = await send_chat_ids(telegram_client(http_client), admin_chat_id())
    logger.info(f"Reported the ids of {found} chat(s)")

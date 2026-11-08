import asyncio
import logging
from typing import Any

import httpx
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, CommandParser

from news_podcast.api.episode.gemini import GeminiClient
from news_podcast.api.episode.service import NewsPodcastService
from news_podcast.api.episode.telegram import TelegramClient

QUIET_LOGGERS = ("httpx", "httpcore", "trafilatura", "htmldate", "charset_normalizer")


class Command(BaseCommand):
    help = "Gera o resumo diário de notícias em áudio e envia no Telegram."
    requires_system_checks: list[str] = []

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--scheduled", action="store_true")
        parser.add_argument("--no-send", action="store_true")

    def handle(self, *args: Any, **options: Any) -> None:
        configure_logging()
        try:
            asyncio.run(
                generate_episode(
                    scheduled=options["scheduled"], send=not options["no_send"]
                )
            )
        except Exception as error:
            raise CommandError(str(error)) from error


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    for name in QUIET_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)


async def generate_episode(*, scheduled: bool, send: bool) -> None:
    api_key = getattr(settings, "GEMINI_API_KEY", None)
    bot_token = getattr(settings, "TELEGRAM_BOT_TOKEN", None)
    chat_id = getattr(settings, "TELEGRAM_CHAT_ID", None) or None

    async with httpx.AsyncClient() as http_client:
        service = NewsPodcastService(
            http_client=http_client,
            gemini=GeminiClient(http_client, api_key) if api_key else None,
            telegram=TelegramClient(http_client, bot_token) if bot_token else None,
            chat_id=chat_id,
        )
        await service.generate_episode(scheduled=scheduled, send=send)

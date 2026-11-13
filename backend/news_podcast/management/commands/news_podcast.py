import asyncio
import logging
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from news_podcast.api.core.telegram import report_chat_ids
from news_podcast.api.episode import run

ACTIONS = ("episode", "chat-id")
QUIET_LOGGERS = ("httpx", "httpcore", "trafilatura", "htmldate", "charset_normalizer")
logger = logging.getLogger(__name__)


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
                run.make_episode(
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

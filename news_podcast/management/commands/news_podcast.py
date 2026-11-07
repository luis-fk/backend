import asyncio
import logging
from typing import Any, get_args

import httpx
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, CommandParser

from news_podcast.api.episode.config import DEFAULT_VOICE
from news_podcast.api.episode.gemini import GeminiClient
from news_podcast.api.episode.options import InvalidOptionError, parse_episode_options
from news_podcast.api.episode.schemas import EpisodeOptions, GeminiPlan, VoiceOption
from news_podcast.api.episode.service import NewsPodcastService, notify_failure
from news_podcast.api.episode.telegram import TelegramClient

ACTIONS = ("episode", "samples", "chat-id")
VOICE_OPTIONS: tuple[VoiceOption, ...] = get_args(VoiceOption)
VOICES_BY_NAME: dict[str, VoiceOption] = {voice: voice for voice in VOICE_OPTIONS}
QUIET_LOGGERS = ("httpx", "httpcore", "trafilatura", "htmldate", "charset_normalizer")


class Command(BaseCommand):
    help = "Gera o resumo diário de notícias em áudio e envia no Telegram."
    requires_system_checks: list[str] = []

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("action", nargs="?", default="episode", choices=ACTIONS)
        parser.add_argument("--scheduled", action="store_true")
        parser.add_argument("--no-send", action="store_true")
        parser.add_argument("--voice", choices=VOICE_OPTIONS)

    def handle(self, *args: Any, **options: Any) -> None:
        configure_logging()
        try:
            asyncio.run(run_action(options))
        except Exception as error:
            raise CommandError(str(error)) from error


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    for name in QUIET_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)


def resolve_voice(option: str | None) -> VoiceOption:
    for candidate in (option, getattr(settings, "NEWS_PODCAST_VOICE", None)):
        voice = VOICES_BY_NAME.get(str(candidate or ""))
        if voice:
            return voice
    return DEFAULT_VOICE


def resolve_plan() -> GeminiPlan:
    configured = getattr(settings, "NEWS_PODCAST_GEMINI_PLAN", None)
    return "paid" if configured == "paid" else "free"


def resolve_episode_options() -> EpisodeOptions:
    return parse_episode_options(
        minutes=getattr(settings, "NEWS_PODCAST_MINUTES", None),
        send_at=getattr(settings, "NEWS_PODCAST_SEND_AT", None),
        speech_speed=getattr(settings, "NEWS_PODCAST_SPEECH_SPEED", None),
    )


async def run_action(options: dict[str, Any]) -> None:
    api_key = getattr(settings, "GEMINI_API_KEY", None)
    bot_token = getattr(settings, "TELEGRAM_BOT_TOKEN", None)
    chat_id = getattr(settings, "TELEGRAM_CHAT_ID", None) or None

    async with httpx.AsyncClient() as http_client:
        telegram = TelegramClient(http_client, bot_token) if bot_token else None
        try:
            episode_options = resolve_episode_options()
        except InvalidOptionError as error:
            if options["action"] == "episode" and not options["no_send"]:
                await notify_failure(telegram, chat_id, "configuração", error)
            raise

        service = NewsPodcastService(
            http_client=http_client,
            gemini=GeminiClient(http_client, api_key) if api_key else None,
            telegram=telegram,
            chat_id=chat_id,
            voice=resolve_voice(options.get("voice")),
            plan=resolve_plan(),
            options=episode_options,
        )

        action = options["action"]
        if action == "samples":
            await service.send_voice_samples()
        elif action == "chat-id":
            found = await service.send_chat_ids()
            logging.getLogger(__name__).info(f"Sent the chat id to {found} chat(s)")
        else:
            await service.generate_episode(
                scheduled=options["scheduled"], send=not options["no_send"]
            )

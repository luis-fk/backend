import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from pytest_django import Settings

from news_podcast.api.core.telegram import admin_chat_id


@pytest.fixture(autouse=True)
def no_keys(settings: Settings) -> None:
    """Keeps the tests away from Gemini and Telegram, even with keys in the .env."""
    settings.GEMINI_API_KEY = None
    settings.TELEGRAM_BOT_TOKEN = None
    settings.TELEGRAM_CHAT_ID = None
    settings.TELEGRAM_ADMIN_CHAT_ID = None


def test_without_an_admin_chat_the_notices_go_to_the_episode_chat(
    settings: Settings,
) -> None:
    settings.TELEGRAM_CHAT_ID = "-22"

    assert admin_chat_id() == "-22"

    settings.TELEGRAM_ADMIN_CHAT_ID = "11"
    assert admin_chat_id() == "11"


def test_the_chat_id_action_fails_without_the_bot_token() -> None:
    with pytest.raises(CommandError, match="TELEGRAM_BOT_TOKEN não configurado"):
        call_command("news_podcast", "chat-id")

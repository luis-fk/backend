from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from pytest_django import Settings

from news_podcast.api.episode import config
from news_podcast.api.episode.schemas import EpisodeReport, Usage
from news_podcast.api.episode.service import EpisodeError, NewsPodcastService
from news_podcast.management.commands.news_podcast import admin_chat_id
from news_podcast.models import Episode, PodcastSettings

# transaction=True: the command closes its connection before writing the history,
# which a test wrapped in a transaction would not survive.
DATABASE = pytest.mark.django_db(
    databases=["default", "news_podcast_db"], transaction=True
)


@pytest.fixture(autouse=True)
def no_keys(settings: Settings) -> None:
    """Keeps the tests away from Gemini and Telegram, even with keys in the .env."""
    settings.GEMINI_API_KEY = None
    settings.TELEGRAM_BOT_TOKEN = None
    settings.TELEGRAM_CHAT_ID = None
    settings.TELEGRAM_ADMIN_CHAT_ID = None


def replace_episode(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Makes a voice answer that costs US$ 6 and a 15-minute episode of 2550 words."""

    async def make(
        service: NewsPodcastService, *, scheduled: bool, send: bool
    ) -> EpisodeReport:
        service.usages.append(
            Usage(step="voice", model=config.TTS_MODEL, output_tokens=1_000_000)
        )
        return EpisodeReport(
            audio_path=tmp_path / "resumo.ogg",
            duration_seconds=900.0,
            caption="🎙️",
            script_words=2550,
        )

    monkeypatch.setattr(NewsPodcastService, "generate_episode", make)


@DATABASE
@pytest.mark.parametrize(
    ("args", "status"),
    [
        (["--scheduled"], Episode.Status.SENT),
        (["--no-send"], Episode.Status.NOT_SENT),
    ],
)
def test_a_run_is_saved_with_its_length_words_and_cost(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    args: list[str],
    status: Episode.Status,
) -> None:
    replace_episode(monkeypatch, tmp_path)

    call_command("news_podcast", "episode", *args)

    episode = Episode.objects.get()
    assert episode.status == status
    assert episode.duration_seconds == 900.0
    assert episode.script_words == 2550
    assert episode.cost_usd == pytest.approx(6.00)
    assert episode.usage == [
        {
            "step": "voice",
            "model": config.TTS_MODEL,
            "input_tokens": 0,
            "output_tokens": 1_000_000,
        }
    ]
    assert episode.error == ""
    # The first run creates the settings with the values in the code.
    assert PodcastSettings.objects.get().text_model == config.TEXT_MODEL


@DATABASE
def test_a_failed_run_keeps_the_step_the_error_and_the_cost_so_far(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fail(
        service: NewsPodcastService, *, scheduled: bool, send: bool
    ) -> EpisodeReport:
        service.usages.append(
            Usage(step="script", model=config.TEXT_MODEL, input_tokens=1_000_000)
        )
        service.step = "voz"
        raise EpisodeError("a cota do dia acabou")

    monkeypatch.setattr(NewsPodcastService, "generate_episode", fail)

    with pytest.raises(CommandError, match="a cota do dia acabou"):
        call_command("news_podcast", "episode", "--scheduled")

    episode = Episode.objects.get()
    assert episode.status == Episode.Status.FAILED
    assert episode.error == "voz: a cota do dia acabou"
    assert episode.duration_seconds is None
    assert episode.cost_usd == pytest.approx(0.75)


@DATABASE
def test_a_paused_podcast_makes_no_episode_on_railway(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    PodcastSettings.objects.create(paused=True)
    replace_episode(monkeypatch, tmp_path)

    call_command("news_podcast", "episode", "--scheduled")
    assert not Episode.objects.exists()

    # A run by hand, without --scheduled, still works.
    call_command("news_podcast", "episode", "--no-send")
    assert Episode.objects.count() == 1


def test_without_an_admin_chat_the_notices_go_to_the_episode_chat(
    settings: Settings,
) -> None:
    settings.TELEGRAM_CHAT_ID = "-22"

    assert admin_chat_id() == "-22"

    settings.TELEGRAM_ADMIN_CHAT_ID = "11"
    assert admin_chat_id() == "11"

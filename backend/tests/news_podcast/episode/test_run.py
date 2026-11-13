from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from pydantic import ValidationError
from pytest_django import Settings

from news_podcast.api.core.schemas import Usage
from news_podcast.api.episode import config, run
from news_podcast.api.episode.schemas import EpisodeReport
from news_podcast.api.episode.service import EpisodeError, EpisodeService
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
        service: EpisodeService, *, scheduled: bool, send: bool
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

    monkeypatch.setattr(EpisodeService, "generate_episode", make)


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
def test_a_run_reads_the_active_feeds_in_the_database(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    read: list[int] = []

    async def make(
        service: EpisodeService, *, scheduled: bool, send: bool
    ) -> EpisodeReport:
        read.append(len(service.sources))
        return EpisodeReport(
            audio_path=tmp_path / "resumo.ogg",
            duration_seconds=900.0,
            caption="🎙️",
            script_words=2550,
        )

    monkeypatch.setattr(EpisodeService, "generate_episode", make)

    call_command("news_podcast", "episode", "--no-send")

    assert read == [len(config.STARTING_FEEDS)]


@DATABASE
def test_a_failed_run_keeps_the_step_the_error_and_the_cost_so_far(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fail(
        service: EpisodeService, *, scheduled: bool, send: bool
    ) -> EpisodeReport:
        service.usages.append(
            Usage(step="script", model=config.TEXT_MODEL, input_tokens=1_000_000)
        )
        service.step = "voz"
        raise EpisodeError("a cota do dia acabou")

    monkeypatch.setattr(EpisodeService, "generate_episode", fail)

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


def test_the_command_makes_the_episode_through_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[bool, bool]] = []

    def make_episode(*, scheduled: bool, send: bool) -> None:
        calls.append((scheduled, send))

    monkeypatch.setattr(run, "make_episode", make_episode)

    call_command("news_podcast", "episode", "--scheduled")
    call_command("news_podcast", "episode", "--no-send")

    assert calls == [(True, True), (False, False)]


def test_the_service_gets_a_frozen_snapshot_of_the_settings() -> None:
    snapshot = run.episode_settings(PodcastSettings())

    assert snapshot.text_models == (config.TEXT_MODEL, config.TEXT_FALLBACK_MODEL)
    assert snapshot.prices[config.TTS_MODEL] == config.TTS_MODEL_PRICE
    with pytest.raises(ValidationError):
        snapshot.voice_model = "outro"  # type: ignore[misc]

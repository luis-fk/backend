import asyncio
import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import DatabaseError
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI
from pydantic import ValidationError
from pytest_django import Settings

from news_podcast.api.core import telegram
from news_podcast.api.core.llm import TextModels
from news_podcast.api.core.schemas import ModelPrice, NewsStory, Usage
from news_podcast.api.core.telegram import TelegramClient
from news_podcast.api.episode import run
from news_podcast.api.episode import service as service_module
from news_podcast.api.episode.schemas import EpisodeReport, NewsItem
from news_podcast.api.episode.service import EpisodeError, EpisodeService
from news_podcast.models import Episode, Feed, PodcastSettings
from tests.news_podcast.factories import build_settings, create_settings
from tests.news_podcast.fake_models import fake_factory

# transaction=True: the command closes its connection before writing the history,
# which a test wrapped in a transaction would not survive.
DATABASE = pytest.mark.django_db(
    databases=["default", "news_podcast_db"], transaction=True
)


@pytest.fixture(autouse=True)
def no_keys(settings: Settings) -> None:
    """Keeps the tests away from the models and Telegram, even with keys in the .env."""
    settings.GEMINI_API_KEY = None
    settings.OPENAI_API_KEY = None
    settings.TELEGRAM_BOT_TOKEN = None
    settings.TELEGRAM_CHAT_ID = None
    settings.TELEGRAM_ADMIN_CHAT_ID = None


def replace_episode(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Makes a voice answer that costs US$ 6 and a 15-minute episode of 2550 words."""

    async def make(
        service: EpisodeService, *, scheduled: bool, send: bool
    ) -> EpisodeReport:
        service.usages.append(
            Usage(
                step="voice",
                model=service.settings.voice_model,
                output_tokens=1_000_000,
            )
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
    row = create_settings()
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
            "model": row.voice_model,
            "input_tokens": 0,
            "output_tokens": 1_000_000,
        }
    ]
    assert episode.error == ""


@DATABASE
def test_a_run_reads_the_active_feeds_in_the_database(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    create_settings()
    for outlet, active in [("g1", True), ("BBC", True), ("Valor", False)]:
        Feed.objects.create(
            outlet=outlet,
            section=Feed.Section.GERAL,
            url=f"https://{outlet.lower()}.example/rss",
            active=active,
        )
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

    assert read == [2]


@DATABASE
def test_a_failed_run_keeps_the_step_the_error_and_the_cost_so_far(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_settings(text_input_price=0.75)

    async def fail(
        service: EpisodeService, *, scheduled: bool, send: bool
    ) -> EpisodeReport:
        model = service.settings.text_models[0]
        service.usages.append(Usage(step="script", model=model, input_tokens=1_000_000))
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


def record_notices(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    """The messages the run's failure notices send, each as (chat, text). A run that
    gets past the settings fails at once, before any request."""
    sent: list[tuple[str, str]] = []

    class RecordingTelegram(TelegramClient):
        async def send_message(self, chat_id: str, text: str) -> None:
            sent.append((chat_id, text))

    async def no_run(
        service: EpisodeService, *, scheduled: bool, send: bool
    ) -> EpisodeReport:
        raise AssertionError("the run must stop at the settings")

    # report_failure looks the client up in core.telegram, not in run.py.
    monkeypatch.setattr(
        telegram, "telegram_client", lambda client: RecordingTelegram(client, "TOKEN")
    )
    monkeypatch.setattr(EpisodeService, "generate_episode", no_run)
    return sent


@DATABASE
def test_without_the_settings_row_the_run_tells_the_admin_to_run_the_seed(
    monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    settings.TELEGRAM_ADMIN_CHAT_ID = "admin"
    sent = record_notices(monkeypatch)

    with pytest.raises(CommandError, match="seed_news_podcast"):
        call_command("news_podcast", "episode", "--scheduled")

    [(chat, text)] = sent
    assert chat == "admin"
    assert "Não consegui gerar o episódio de hoje" in text
    assert "<b>Etapa:</b> configurações" in text
    assert "seed_news_podcast" in text
    assert not Episode.objects.exists()
    assert not PodcastSettings.objects.exists()


@DATABASE
def test_without_the_settings_row_a_run_without_sending_only_fails(
    monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    settings.TELEGRAM_ADMIN_CHAT_ID = "admin"
    sent = record_notices(monkeypatch)

    with pytest.raises(CommandError, match="seed_news_podcast"):
        call_command("news_podcast", "episode", "--no-send")

    assert sent == []
    assert not Episode.objects.exists()


@DATABASE
def test_with_no_feeds_the_run_fails_at_reading_them(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    create_settings()

    async def fetch(
        http_client: httpx.AsyncClient, sources: list[Any], *_window: object
    ) -> list[NewsItem]:
        assert sources == []
        return []

    monkeypatch.setattr(service_module, "fetch_items", fetch)
    monkeypatch.setattr(service_module, "OUTPUT_DIR", tmp_path)

    with pytest.raises(CommandError, match="Nenhuma notícia encontrada nos feeds"):
        call_command("news_podcast", "episode", "--no-send")

    episode = Episode.objects.get()
    assert episode.status == Episode.Status.FAILED
    assert episode.error == "leitura dos feeds: Nenhuma notícia encontrada nos feeds"
    assert not Feed.objects.exists()


@DATABASE
def test_a_paused_podcast_makes_no_episode_on_railway(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    create_settings(paused=True)
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
    row = build_settings()

    snapshot = run.episode_settings(row)

    assert snapshot.text_models == (row.text_model, row.fallback_model)
    assert snapshot.prices[row.voice_model] == ModelPrice(
        row.voice_input_price, row.voice_output_price
    )
    with pytest.raises(ValidationError):
        snapshot.voice_model = "outro"  # type: ignore[misc]


STORIES = json.dumps(
    {
        "stories": [
            {
                "title": "Juros sobem",
                "category": "economia",
                "minutes": 2,
                "angle": "o que muda no crédito",
                "item_ids": ["1"],
            },
            {
                "title": "Chuva no Sul",
                "category": "geral",
                "minutes": 1,
                "angle": "",
                "item_ids": ["2"],
            },
        ]
    }
)


def news_items() -> list[NewsItem]:
    return [
        NewsItem(
            id=item_id,
            outlet="g1",
            section="Política",
            title=title,
            summary="",
            link="",
            published_at=None,
        )
        for item_id, title in (("1", "Juros sobem"), ("2", "Chuva no Sul"))
    ]


@DATABASE
def test_select_today_returns_the_days_stories_and_makes_no_episode(
    monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    settings.GEMINI_API_KEY = "test-key"
    row = create_settings()
    Feed.objects.create(
        outlet="g1", section=Feed.Section.POLITICA, url="https://g1.globo.com/rss/g1/"
    )
    read: list[int] = []

    async def fetch(
        http_client: httpx.AsyncClient, sources: list[Any], *_window: object
    ) -> list[NewsItem]:
        read.append(len(sources))
        return news_items()

    def no_telegram(*_args: object) -> None:
        raise AssertionError("select_today sends nothing")

    monkeypatch.setattr(run, "fetch_items", fetch)
    monkeypatch.setattr(run, "telegram_client", no_telegram)

    selection = run.select_today(
        model_factory=fake_factory({row.text_model: [STORIES]}, [])
    )

    assert selection.error is None
    assert selection.stories == [
        NewsStory("Juros sobem", "economia", "o que muda no crédito"),
        NewsStory("Chuva no Sul", "geral", ""),
    ]
    assert [(usage.step, usage.model) for usage in selection.usages] == [
        ("selection", row.text_model)
    ]
    assert read == [1]
    assert not Episode.objects.exists()


@DATABASE
@pytest.mark.parametrize(
    "failure", ["settings", "feeds", "window", "no news", "no answer"]
)
def test_select_today_returns_the_error_instead_of_raising(
    monkeypatch: pytest.MonkeyPatch, settings: Settings, failure: str
) -> None:
    settings.GEMINI_API_KEY = "test-key"
    row = create_settings()

    async def fetch(*_args: object) -> list[NewsItem]:
        return [] if failure == "no news" else news_items()

    def broken() -> PodcastSettings:
        raise DatabaseError("a conexão caiu")

    monkeypatch.setattr(run, "fetch_items", fetch)
    if failure == "settings":
        monkeypatch.setattr(PodcastSettings, "load", broken)
    if failure == "feeds":
        monkeypatch.setattr(Feed, "sources", broken)
    if failure == "window":
        monkeypatch.setattr(run, "news_window", broken)
    no_stories = '{"stories": []}'
    outcomes = {
        row.text_model: [no_stories] * 2,
        row.fallback_model: [no_stories] * 2,
    }

    selection = run.select_today(model_factory=fake_factory(outcomes, []))

    assert selection.stories == []
    assert selection.error is not None
    assert len(selection.usages) == (4 if failure == "no answer" else 0)


def test_each_run_builds_its_own_text_models_and_clients(
    monkeypatch: pytest.MonkeyPatch, settings: Settings, tmp_path: Path
) -> None:
    settings.OPENAI_API_KEY = "test-key"
    openai = "openai:gpt-4.1-mini"
    snapshot = run.episode_settings(build_settings()).model_copy(
        update={"text_models": (openai,)}
    )
    seen: list[tuple[TextModels, httpx.AsyncClient, BaseChatModel]] = []

    async def capture(
        service: EpisodeService, *, scheduled: bool, send: bool
    ) -> EpisodeReport:
        seen.append((service.text, service.http_client, service.text.model(openai)))
        return EpisodeReport(
            audio_path=tmp_path / "resumo.ogg",
            duration_seconds=1.0,
            caption="🎙️",
            script_words=1,
        )

    monkeypatch.setattr(EpisodeService, "generate_episode", capture)

    for _ in range(2):
        asyncio.run(run.generate(snapshot, [], scheduled=False, send=False))

    (text_a, client_a, model_a), (text_b, client_b, model_b) = seen
    assert text_a is not text_b
    assert client_a is not client_b
    assert model_a is not model_b
    assert isinstance(model_a, ChatOpenAI)
    assert isinstance(model_b, ChatOpenAI)
    assert model_a.http_async_client is client_a
    assert model_b.http_async_client is client_b

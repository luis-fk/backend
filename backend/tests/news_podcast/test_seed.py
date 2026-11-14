import json
import re
import shutil
from datetime import date, datetime, time
from io import StringIO
from pathlib import Path
from typing import Any

import pytest
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from langchain_core.prompts import ChatPromptTemplate

from news_podcast.api.core.config import LOCAL_TZ
from news_podcast.api.core.schemas import Script, Turn
from news_podcast.api.episode.config import STARTING_FEEDS
from news_podcast.api.episode.prompts import (
    lengthening_template,
    script_template,
    selection_template,
)
from news_podcast.api.episode.schemas import EpisodeOptions
from news_podcast.api.episode.script import lengthening_values, script_values
from news_podcast.api.episode.selection import selection_values
from news_podcast.models import STARTING_VALUES, Feed, PodcastSettings

DATABASES = pytest.mark.django_db(databases=["default", "news_podcast_db"])
SEED_DIR = Path(__file__).resolve().parents[2] / "news_podcast" / "seed"
COMMAND = "news_podcast.management.commands.seed_news_podcast"
# The morning episode: the news from 6:00 to 6:00, sent at 7:00 on a Friday.
MORNING_START = datetime(2026, 11, 5, 6, 0, tzinfo=LOCAL_TZ)
MORNING_END = datetime(2026, 11, 6, 6, 0, tzinfo=LOCAL_TZ)
LOCAL = {"ENGINE": "django.db.backends.postgresql", "HOST": "localhost"}
REMOTE = {
    "ENGINE": "django.db.backends.postgresql",
    "HOST": "x.proxy.rlwy.net",
    "PASSWORD": "secret-password",
}


def read(folder: Path, name: str) -> Any:
    return json.loads((folder / name).read_text(encoding="utf-8"))


def write(folder: Path, name: str, data: Any) -> None:
    (folder / name).write_text(json.dumps(data), encoding="utf-8")


def seed(**options: Any) -> str:
    out = StringIO()
    call_command("seed_news_podcast", stdout=out, **options)
    return out.getvalue()


def answer(monkeypatch: pytest.MonkeyPatch, reply: str) -> list[str]:
    """Answers the confirmation with reply and returns the prompts shown."""
    prompts: list[str] = []

    def typed(prompt: str = "") -> str:
        prompts.append(prompt)
        return reply

    monkeypatch.setattr("builtins.input", typed)
    return prompts


def nothing_written() -> bool:
    return not PodcastSettings.objects.exists() and not Feed.objects.exists()


def morning_options() -> EpisodeOptions:
    return PodcastSettings(**read(SEED_DIR, "settings.json")).episode_options()


def system_message(template: ChatPromptTemplate, values: dict[str, Any]) -> str:
    return str(template.format_messages(**values)[0].content)


@pytest.fixture
def seed_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A copy of the committed seed files, which the command reads instead, so a test
    can break one."""
    for name in ("settings.json", "feeds.json"):
        shutil.copy(SEED_DIR / name, tmp_path / name)
    monkeypatch.setattr(f"{COMMAND}.SEED_DIR", tmp_path)
    return tmp_path


def test_the_seed_settings_are_the_starting_values_in_the_code() -> None:
    assert read(SEED_DIR, "settings.json") == {"paused": False, **STARTING_VALUES}


def test_the_seed_feeds_are_the_starting_feeds_in_the_code() -> None:
    feeds = read(SEED_DIR, "feeds.json")

    assert [(feed["outlet"], feed["section"], feed["url"]) for feed in feeds] == list(
        STARTING_FEEDS
    )
    assert all(feed["active"] is True for feed in feeds)


def test_the_seed_settings_pass_the_admin_checks() -> None:
    PodcastSettings(**read(SEED_DIR, "settings.json")).full_clean()


def test_the_seed_feeds_have_unique_urls_and_known_sections() -> None:
    feeds = read(SEED_DIR, "feeds.json")
    urls = [feed["url"] for feed in feeds]

    assert len(set(urls)) == len(urls)
    assert {feed["section"] for feed in feeds} <= set(Feed.Section.values)


def test_the_seed_prompts_leave_the_answer_format_to_the_schema() -> None:
    values = read(SEED_DIR, "settings.json")

    for name in ("selection_prompt", "script_prompt", "expand_prompt"):
        assert "JSON" not in values[name]
        assert '"' + "item_ids" not in values[name]


def test_the_seed_selection_prompt_keeps_the_morning_episode() -> None:
    selection = system_message(
        selection_template(read(SEED_DIR, "settings.json")["selection_prompt"]),
        {
            "headlines": "",
            **selection_values(morning_options(), MORNING_START, MORNING_END),
        },
    )

    assert "Escolha de 8 a 12 histórias" in selection


def test_the_seed_selection_weighs_how_many_outlets_reported_a_fact() -> None:
    selection = " ".join(read(SEED_DIR, "settings.json")["selection_prompt"].split())

    assert "quantos veículos diferentes" in selection
    assert "Conte cada veículo uma vez" in selection


def test_the_seed_script_prompt_keeps_the_morning_episode() -> None:
    script = system_message(
        script_template(read(SEED_DIR, "settings.json")["script_prompt"]),
        {
            "briefs": "",
            **script_values(
                morning_options(),
                date(2026, 11, 6),
                MORNING_START,
                MORNING_END,
                time(7, 0),
            ),
        },
    )

    assert 'chamado "Resumo das 7"' in script
    assert "É o episódio das 7h de sexta-feira, 6 de novembro" in script
    assert "uma fala curta com bom dia e a data" in script
    assert "entre 2040 e 3060 palavras" in script


def test_the_seed_expand_prompt_fills_every_placeholder() -> None:
    values = read(SEED_DIR, "settings.json")
    script = Script(turns=[Turn(speaker="Bia", text="Bom dia")])
    filled = {
        "briefs": "",
        **script_values(
            morning_options(), date(2026, 11, 6), MORNING_START, MORNING_END, time(7, 0)
        ),
        **lengthening_values(morning_options(), script),
    }

    _, human = lengthening_template(
        values["script_prompt"], values["expand_prompt"]
    ).format_messages(**filled)

    assert "ficou com 2 palavras, mas precisa ter entre 2040 e 3060" in str(
        human.content
    )
    assert script.model_dump_json() in str(human.content)


@DATABASES
def test_an_empty_database_gets_the_seed_settings_and_feeds() -> None:
    out = seed()

    row = PodcastSettings.objects.get()
    values = read(SEED_DIR, "settings.json")
    assert {name: getattr(row, name) for name in values} == values
    feeds = [
        {"outlet": f.outlet, "section": f.section, "url": f.url, "active": f.active}
        for f in Feed.objects.order_by("pk")
    ]
    assert feeds == read(SEED_DIR, "feeds.json")
    assert "news_podcast: settings created from seed/settings.json" in out
    assert f"news_podcast: {len(feeds)} feeds created from seed/feeds.json" in out


@DATABASES
def test_a_second_run_leaves_the_rows_as_they_are() -> None:
    seed()
    PodcastSettings.objects.update(max_minutes=20, script_prompt="{min_words}")
    Feed.objects.filter(outlet="g1").update(active=False)
    Feed.objects.create(
        outlet="Agência Brasil",
        section=Feed.Section.GERAL,
        url="https://agenciabrasil.ebc.com.br/rss/ultimasnoticias/feed.xml",
    )
    settings_before = list(PodcastSettings.objects.values())
    feeds_before = list(Feed.objects.order_by("pk").values())

    out = seed()

    assert list(PodcastSettings.objects.values()) == settings_before
    assert list(Feed.objects.order_by("pk").values()) == feeds_before
    assert "news_podcast: the settings row already exists; left as it was" in out
    assert "news_podcast: the feed list isn't empty; left as it was" in out


@DATABASES
def test_an_empty_feed_list_is_filled_and_the_settings_row_kept() -> None:
    seed()
    Feed.objects.all().delete()
    PodcastSettings.objects.update(max_minutes=20)

    seed()

    assert PodcastSettings.objects.get().max_minutes == 20
    assert Feed.objects.count() == len(read(SEED_DIR, "feeds.json"))


@DATABASES
def test_a_list_of_inactive_feeds_is_not_filled_again() -> None:
    Feed.objects.create(
        outlet="g1",
        section=Feed.Section.GERAL,
        url="https://g1.globo.com/rss/g1/",
        active=False,
    )

    seed()

    assert Feed.objects.count() == 1


@DATABASES
def test_a_remote_database_stops_the_seed_before_it_writes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        settings, "DATABASES", {"default": LOCAL, "news_podcast_db": REMOTE}
    )
    prompts = answer(monkeypatch, "yes")

    with pytest.raises(CommandError) as error:
        seed()

    assert "news_podcast_db (x.proxy.rlwy.net)" in str(error.value)
    assert "secret-password" not in str(error.value)
    assert prompts == []
    assert nothing_written()


@DATABASES
def test_production_shows_the_address_and_seeds_after_a_yes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    production = {**REMOTE, "PORT": 5432, "NAME": "news_podcast"}
    monkeypatch.setattr(
        settings, "DATABASES", {"default": REMOTE, "news_podcast_db": production}
    )
    prompts = answer(monkeypatch, "yes")

    out = seed(production=True)

    assert len(prompts) == 1
    assert "news_podcast_db: x.proxy.rlwy.net:5432/news_podcast" in out
    assert "secret-password" not in out + prompts[0]
    assert PodcastSettings.objects.count() == 1
    assert Feed.objects.count() == len(read(SEED_DIR, "feeds.json"))


@DATABASES
def test_production_writes_nothing_without_a_yes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        settings, "DATABASES", {"default": REMOTE, "news_podcast_db": REMOTE}
    )
    answer(monkeypatch, "y")

    with pytest.raises(CommandError, match="Nothing was written"):
        seed(production=True)

    assert nothing_written()


@DATABASES
def test_a_settings_file_without_a_field_stops_the_seed(seed_dir: Path) -> None:
    values = read(seed_dir, "settings.json")
    del values["max_minutes"]
    write(seed_dir, "settings.json", values)

    with pytest.raises(CommandError, match="seed/settings.json lacks max_minutes"):
        seed()

    assert nothing_written()


@DATABASES
def test_a_settings_file_with_an_unknown_field_stops_the_seed(seed_dir: Path) -> None:
    values = read(seed_dir, "settings.json")
    values["duracao_maxima"] = 18
    write(seed_dir, "settings.json", values)

    with pytest.raises(CommandError, match="unknown fields: duracao_maxima"):
        seed()

    assert nothing_written()


@DATABASES
def test_a_null_number_is_named_instead_of_crashing(seed_dir: Path) -> None:
    values = read(seed_dir, "settings.json")
    values["max_minutes"] = None
    write(seed_dir, "settings.json", values)

    with pytest.raises(CommandError, match="max_minutes: This field cannot be null"):
        seed()

    assert nothing_written()


@DATABASES
def test_a_prompt_with_a_placeholder_its_step_lacks_stops_the_seed(
    seed_dir: Path,
) -> None:
    values = read(seed_dir, "settings.json")
    values["selection_prompt"] += " Fale com {nome}."
    write(seed_dir, "settings.json", values)

    with pytest.raises(CommandError, match=r"selection_prompt: Unknown placeholder"):
        seed()

    assert nothing_written()


@DATABASES
@pytest.mark.parametrize("field", ["outlet", "section", "url", "active"])
def test_a_feed_without_a_field_stops_the_seed(seed_dir: Path, field: str) -> None:
    feeds = read(seed_dir, "feeds.json")
    del feeds[1][field]
    write(seed_dir, "feeds.json", feeds)

    with pytest.raises(CommandError, match=f"seed/feeds.json, entry 2 lacks {field}"):
        seed()

    assert nothing_written()


@DATABASES
def test_a_feed_in_an_unknown_section_stops_the_seed(seed_dir: Path) -> None:
    feeds = read(seed_dir, "feeds.json")
    feeds[0]["section"] = "Esportes"
    write(seed_dir, "feeds.json", feeds)

    with pytest.raises(CommandError, match="entry 1: section"):
        seed()

    assert nothing_written()


@DATABASES
def test_a_repeated_feed_url_stops_the_seed(seed_dir: Path) -> None:
    feeds = read(seed_dir, "feeds.json")
    feeds.append({**feeds[0], "outlet": "Outro"})
    write(seed_dir, "feeds.json", feeds)

    with pytest.raises(CommandError, match=f"repeats {re.escape(feeds[0]['url'])}"):
        seed()

    assert nothing_written()


@DATABASES
def test_a_broken_seed_file_is_named(seed_dir: Path) -> None:
    (seed_dir / "feeds.json").write_text("[{", encoding="utf-8")

    with pytest.raises(CommandError, match="seed/feeds.json isn't valid JSON"):
        seed()

    assert nothing_written()

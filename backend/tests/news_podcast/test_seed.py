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
from news_podcast.api.episode.prompts import (
    lengthening_template,
    script_template,
    selection_template,
)
from news_podcast.api.episode.schemas import EpisodeOptions
from news_podcast.api.episode.script import lengthening_values, script_values
from news_podcast.api.episode.selection import selection_values
from news_podcast.models import Area, Feed, PodcastSettings, Topic
from tests.news_podcast.factories import create_area, create_topic

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
    "USER": "secret-user",
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
    return not (
        PodcastSettings.objects.exists()
        or Feed.objects.exists()
        or Area.objects.exists()
        or Topic.objects.exists()
    )


def morning_options() -> EpisodeOptions:
    return PodcastSettings(**read(SEED_DIR, "settings.json")).episode_options()


def system_message(template: ChatPromptTemplate, values: dict[str, Any]) -> str:
    return str(template.format_messages(**values)[0].content)


@pytest.fixture
def seed_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A copy of the committed seed files, which the command reads instead, so a test
    can break one."""
    for name in ("settings.json", "feeds.json", "catalog.json"):
        shutil.copy(SEED_DIR / name, tmp_path / name)
    monkeypatch.setattr(f"{COMMAND}.SEED_DIR", tmp_path)
    return tmp_path


def test_the_seed_catalog_has_the_design_s_areas_and_topics() -> None:
    catalog = read(SEED_DIR, "catalog.json")
    titles = [title for area in catalog for title in area["topics"]]

    assert [len(area["topics"]) for area in catalog] == [15, 14, 22, 13, 11, 20, 6]
    assert len(titles) == 101
    assert all(isinstance(title, str) and title.strip() for title in titles)
    assert len(set(titles)) == len(titles)


def test_the_seed_settings_pass_the_admin_checks() -> None:
    PodcastSettings(**read(SEED_DIR, "settings.json")).full_clean()


def test_the_seed_feeds_are_active_with_unique_urls_and_known_sections() -> None:
    feeds = read(SEED_DIR, "feeds.json")
    urls = [feed["url"] for feed in feeds]

    assert all(feed["active"] is True for feed in feeds)
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
def test_an_empty_catalog_gets_the_seed_areas_and_topics_in_teaching_order() -> None:
    out = seed()

    areas = list(Area.objects.all())
    catalog = [
        {"name": area.name, "topics": [topic.title for topic in area.topics.all()]}
        for area in areas
    ]
    assert catalog == read(SEED_DIR, "catalog.json")
    assert [area.position for area in areas] == list(range(1, 8))
    for area in areas:
        positions = [topic.position for topic in area.topics.all()]
        assert positions == list(range(1, len(positions) + 1))
    assert areas[0].name == "Os Poderes e o Estado"
    assert (
        areas[0].topics.get(position=1).title
        == "Os três Poderes e os freios e contrapesos entre eles"
    )
    assert areas[6].name == "O Brasil no mundo"
    assert areas[6].topics.get(position=6).title == "BRICS: o que é o grupo"
    assert Topic.objects.filter(active=True).count() == 101
    assert "news_podcast: 7 areas and 101 topics created from seed/catalog.json" in out


@DATABASES
@pytest.mark.parametrize("production", [False, True])
def test_a_catalog_with_an_area_is_left_as_it_is(
    monkeypatch: pytest.MonkeyPatch, production: bool
) -> None:
    area = create_area(name="Minha área", position=9)
    create_topic(area, title="Meu tópico", position=3, active=False)
    before = (list(Area.objects.values()), list(Topic.objects.values()))
    if production:
        monkeypatch.setattr(
            settings, "DATABASES", {"default": REMOTE, "news_podcast_db": REMOTE}
        )
        answer(monkeypatch, "yes")

    out = seed(production=production)

    assert (list(Area.objects.values()), list(Topic.objects.values())) == before
    assert "news_podcast: the catalog isn't empty; left as it was" in out


@DATABASES
def test_an_empty_catalog_is_filled_and_the_other_tables_kept() -> None:
    seed()
    Area.objects.all().delete()
    PodcastSettings.objects.update(max_minutes=20)

    seed()

    assert PodcastSettings.objects.get().max_minutes == 20
    assert Topic.objects.count() == 101


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
    assert "secret-user" not in str(error.value)
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
    assert "secret-user" not in out + prompts[0]
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
@pytest.mark.parametrize(
    ("field", "value", "kind"),
    [
        ("max_minutes", None, "a whole number"),
        ("fallback_model", None, "text"),
        ("min_minutes", 12.7, "a whole number"),
        ("max_minutes", True, "a whole number"),
        ("max_minutes", float("inf"), "a whole number"),
        ("speech_speed", True, "a number"),
        ("speech_speed", float("nan"), "a number"),
        ("text_input_price", "0.75", "a number"),
        ("expand_prompt", ["Roteiro:", "{script}"], "text"),
        ("voice_model", {"google_genai": "gemini-3.8-flash-lite-tts"}, "text"),
        ("paused", 0, "true or false"),
    ],
)
def test_a_value_of_the_wrong_json_type_stops_the_seed(
    seed_dir: Path, field: str, value: Any, kind: str
) -> None:
    values = read(seed_dir, "settings.json")
    values[field] = value
    write(seed_dir, "settings.json", values)

    with pytest.raises(CommandError, match=f"settings.json: {field} must be {kind}"):
        seed()

    assert nothing_written()


@DATABASES
@pytest.mark.parametrize(
    ("field", "value", "kind"),
    [
        ("outlet", 360, "text"),
        ("url", None, "text"),
        ("active", "sim", "true or false"),
    ],
)
def test_a_feed_value_of_the_wrong_json_type_stops_the_seed(
    seed_dir: Path, field: str, value: Any, kind: str
) -> None:
    feeds = read(seed_dir, "feeds.json")
    feeds[2][field] = value
    write(seed_dir, "feeds.json", feeds)

    with pytest.raises(CommandError, match=f"entry 3: {field} must be {kind}"):
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
@pytest.mark.parametrize(
    ("name", "content", "message"),
    [
        ("feeds.json", "[{", "seed/feeds.json can't be read"),
        ("feeds.json", None, "seed/feeds.json can't be read"),
        ("settings.json", "[]", "seed/settings.json isn't a JSON object"),
        ("feeds.json", "[]", "seed/feeds.json must be a list of feeds"),
        ("feeds.json", '{"outlet": "g1"}', "seed/feeds.json must be a list of feeds"),
        ("feeds.json", "[null]", "seed/feeds.json, entry 1 isn't a JSON object"),
        ("catalog.json", None, "seed/catalog.json can't be read"),
        ("catalog.json", "[]", "seed/catalog.json must be a list of areas"),
        ("catalog.json", '{"name": "x"}', "seed/catalog.json must be a list of areas"),
        (
            "catalog.json",
            '[{"name": "Justiça"}]',
            "seed/catalog.json, area 1 must have name and topics, and nothing else",
        ),
        (
            "catalog.json",
            '[{"name": 7, "topics": ["O STF"]}]',
            "seed/catalog.json, area 1: name must be text",
        ),
        (
            "catalog.json",
            '[{"name": "Justiça", "topics": []}]',
            "seed/catalog.json, area 1: topics must be a list of titles",
        ),
        (
            "catalog.json",
            '[{"name": "Justiça", "topics": ["O STF", 7]}]',
            "seed/catalog.json, area 1: topics must be a list of titles",
        ),
        (
            "catalog.json",
            '[{"name": "", "topics": ["O STF"]}]',
            "seed/catalog.json, area 1: name: This field cannot be blank.",
        ),
        (
            "catalog.json",
            '[{"name": "Justiça", "topics": ["O STF", ""]}]',
            "seed/catalog.json, area 1, topic 2: title: This field cannot be blank.",
        ),
        (
            "catalog.json",
            json.dumps([{"name": "Justiça", "topics": ["x" * 201]}]),
            "seed/catalog.json, area 1, topic 1: title: Ensure this value has at "
            "most 200 characters",
        ),
    ],
)
def test_a_seed_file_of_the_wrong_shape_stops_the_seed(
    seed_dir: Path, name: str, content: str | None, message: str
) -> None:
    if content is None:
        (seed_dir / name).unlink()
    else:
        (seed_dir / name).write_text(content, encoding="utf-8")

    with pytest.raises(CommandError, match=re.escape(message)):
        seed()

    assert nothing_written()


@DATABASES
def test_a_broken_file_stops_production_before_the_question(
    seed_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    values = read(seed_dir, "settings.json")
    del values["max_minutes"]
    write(seed_dir, "settings.json", values)
    monkeypatch.setattr(
        settings, "DATABASES", {"default": REMOTE, "news_podcast_db": REMOTE}
    )
    prompts = answer(monkeypatch, "yes")

    with pytest.raises(CommandError, match="lacks max_minutes"):
        seed(production=True)

    assert prompts == []
    assert nothing_written()


@DATABASES
def test_a_seeded_database_still_has_its_files_checked(seed_dir: Path) -> None:
    seed()
    feeds = read(seed_dir, "feeds.json")
    feeds[0]["section"] = "Esportes"
    write(seed_dir, "feeds.json", feeds)

    with pytest.raises(CommandError, match="entry 1: section"):
        seed()

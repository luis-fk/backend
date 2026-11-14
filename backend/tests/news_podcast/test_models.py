from datetime import UTC, datetime
from typing import Any

import pytest
from django.core.exceptions import ValidationError
from django.db import connections
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.loader import MigrationLoader
from django.db.models import ProtectedError

from news_podcast.api.core.schemas import ModelPrice
from news_podcast.api.episode.schemas import EpisodeOptions
from news_podcast.models import (
    LESSON_PROMPT_FIELDS,
    Area,
    Episode,
    Feed,
    LessonSettings,
    PodcastSettings,
    SettingsMissing,
    Topic,
    placeholder_error,
)
from tests.news_podcast.factories import (
    LESSON_SETTINGS,
    SETTINGS,
    build_lesson_settings,
    build_settings,
    create_area,
    create_lesson_row,
    create_topic,
)

DATABASES = pytest.mark.django_db(databases=["default", "news_podcast_db"])
SQUASH = ("news_podcast", "0001_squashed_0007_no_code_defaults")


def test_the_factory_builds_a_complete_row_that_passes_the_admin_checks() -> None:
    editable = {
        field.name
        for field in PodcastSettings._meta.concrete_fields
        if field.editable and not field.primary_key
    }

    assert set(SETTINGS) == editable
    build_settings().full_clean()


def test_only_paused_has_a_default() -> None:
    defaults = [
        field.name
        for field in PodcastSettings._meta.concrete_fields
        if field.has_default()
    ]

    assert defaults == ["paused"]


def test_the_settings_give_the_options_and_each_model_s_price() -> None:
    podcast_settings = build_settings()

    assert podcast_settings.episode_options() == EpisodeOptions(12, 18, 1.0)
    assert podcast_settings.prices() == {
        "gemini-text": ModelPrice(0.75, 3.75),
        "gemini-fallback": ModelPrice(0.5, 2.0),
        "gemini-voice": ModelPrice(0.5, 6.0),
    }


def test_without_a_fallback_only_the_text_model_writes() -> None:
    podcast_settings = build_settings(fallback_model="")

    assert podcast_settings.text_models() == [podcast_settings.text_model]
    assert "" not in podcast_settings.prices()


@pytest.mark.parametrize(
    ("values", "field", "message"),
    [
        ({"min_minutes": 3}, "min_minutes", "greater than or equal to 5"),
        ({"min_minutes": 18, "max_minutes": 12}, "max_minutes", "less than the min"),
        ({"speech_speed": 0.25}, "speech_speed", "greater than or equal to 0.5"),
        (
            {"max_minutes": 18, "speech_speed": 2.0},
            "max_minutes",
            "36 minutes of speech",
        ),
        ({"script_prompt": "Oi, {ouvinte}!"}, "script_prompt", "{ouvinte}"),
        ({"expand_prompt": "Roteiro: {script"}, "expand_prompt", "literal brace"),
        ({"selection_prompt": 'Use {"stories": []}'}, "selection_prompt", "{{"),
        ({"script_prompt": "Hoje, {today:%d/%m}"}, "script_prompt", "without a format"),
        (
            {"expand_prompt": "{min_words!r} palavras"},
            "expand_prompt",
            "without a format",
        ),
    ],
)
def test_invalid_settings_say_what_is_wrong(
    values: dict[str, Any], field: str, message: str
) -> None:
    with pytest.raises(ValidationError) as caught:
        build_settings(**values).full_clean()

    assert message in " ".join(caught.value.message_dict[field])


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("min_minutes", None, "cannot be null"),
        ("max_minutes", None, "cannot be null"),
        ("speech_speed", "rápido", "must be a float"),
        ("selection_prompt", None, "cannot be null"),
        ("text_model", ["google_genai:gemini-3.8-flash"] * 4, "at most 100"),
        ("voice_model", ["google_genai:gemini-3.8-flash-lite-tts"] * 3, "at most 100"),
    ],
)
def test_a_value_of_the_wrong_type_is_named_instead_of_crashing_clean(
    field: str, value: Any, message: str
) -> None:
    with pytest.raises(ValidationError) as caught:
        build_settings(**{field: value}).full_clean()

    assert message in " ".join(caught.value.message_dict[field])


def test_a_prompt_may_use_its_placeholders_and_doubled_braces() -> None:
    build_settings(
        script_prompt='{podcast_name}, com {host_a}: {{"turns": []}}'
    ).full_clean()


@pytest.mark.parametrize("field", ["text_model", "fallback_model"])
@pytest.mark.parametrize(
    "name",
    [
        "anthropic:claude-x",
        "google_vertexai:gemini-3.8-flash",
        "gpt-4.1-mini",
        "openai:",
        "google_genai:",
        "openai: gpt-4.1-mini",
    ],
)
def test_a_text_model_needs_a_provider_the_podcast_knows(field: str, name: str) -> None:
    with pytest.raises(ValidationError) as caught:
        build_settings(**{field: name}).full_clean()

    message = " ".join(caught.value.message_dict[field])
    assert "google_genai" in message
    assert "openai" in message


@pytest.mark.parametrize(
    "name",
    ["gemini-3.8-flash", "google_genai:gemini-3.8-flash", "openai:gpt-4.1-mini"],
)
def test_a_text_model_is_a_bare_gemini_name_or_provider_model(name: str) -> None:
    build_settings(text_model=name, fallback_model=name).full_clean()


def test_the_fallback_model_may_be_empty() -> None:
    build_settings(fallback_model="").full_clean()


@pytest.mark.parametrize(
    "name",
    [
        "openai:gpt-4o-mini-tts",
        "eleven-v3",
        "google_genai:",
        "google_vertexai:gemini-3.8-flash-lite-tts",
    ],
)
def test_the_voice_model_needs_a_voice_provider(name: str) -> None:
    with pytest.raises(ValidationError) as caught:
        build_settings(voice_model=name).full_clean()

    message = " ".join(caught.value.message_dict["voice_model"])
    assert "google_genai" in message
    assert "openai" not in message


@pytest.mark.parametrize(
    "name", ["gemini-3.8-flash-lite-tts", "google_genai:gemini-3.8-flash-lite-tts"]
)
def test_the_voice_model_is_a_bare_gemini_name_or_provider_model(name: str) -> None:
    build_settings(voice_model=name).full_clean()


@DATABASES
def test_a_google_news_feed_is_read_through_google_news() -> None:
    Feed.objects.create(
        outlet="ICL Notícias",
        section=Feed.Section.GERAL,
        url="https://news.google.com/rss/search?q=site:iclnoticias.com.br+when:2d",
    )
    Feed.objects.create(
        outlet="g1", section=Feed.Section.POLITICA, url="https://g1.globo.com/rss/g1/"
    )

    sources = {source.outlet: source for source in Feed.sources()}

    assert sources["ICL Notícias"].via_google_news
    assert not sources["g1"].via_google_news


@DATABASES
def test_feeds_are_read_in_section_order() -> None:
    for outlet, section in [
        ("g1", Feed.Section.POLITICA),
        ("BBC", Feed.Section.GERAL),
        ("Valor", Feed.Section.ECONOMIA),
    ]:
        Feed.objects.create(
            outlet=outlet, section=section, url=f"https://{outlet.lower()}.example/rss"
        )

    sections = [source.section for source in Feed.sources()]

    # Of a headline in two feeds of one outlet, the first feed's copy stays.
    assert sections == ["Economia", "Geral", "Política"]


@DATABASES
def test_feeds_turned_off_are_not_read() -> None:
    Feed.objects.create(
        outlet="g1",
        section=Feed.Section.GERAL,
        url="https://g1.globo.com/rss/g1/",
        active=False,
    )

    assert Feed.sources() == []


@DATABASES
def test_without_a_row_load_says_to_run_the_seed_and_creates_none() -> None:
    with pytest.raises(SettingsMissing, match="seed_news_podcast"):
        PodcastSettings.load()

    assert not PodcastSettings.objects.exists()


@DATABASES
def test_an_empty_feed_list_stays_empty() -> None:
    assert Feed.sources() == []
    assert not Feed.objects.exists()


@DATABASES
def test_areas_and_topics_keep_one_order_through_ties() -> None:
    later = create_area(name="Justiça", position=2)
    first = create_area(name="O Congresso e as leis", position=1)
    tied = create_area(name="Eleições e partidos", position=1)
    create_topic(first, title="B", position=1)
    create_topic(first, title="A", position=1)
    create_topic(tied, title="C", position=0)
    create_topic(later, title="D", position=1)
    # An update moves a row to the end of its table on PostgreSQL, so the tied rows
    # created first no longer come back first on their own: only the pk orders them.
    Area.objects.filter(pk=first.pk).update(position=1)
    Topic.objects.filter(title="B").update(position=1)

    assert list(Area.objects.values_list("name", flat=True)) == [
        "O Congresso e as leis",
        "Eleições e partidos",
        "Justiça",
    ]
    # An area's topics stay together, even when two areas share a position.
    assert list(Topic.objects.values_list("title", flat=True)) == ["B", "A", "C", "D"]


@DATABASES
def test_the_taught_date_keeps_the_teaching_order() -> None:
    area = create_area()
    for position in (3, 1, 2):
        create_topic(area, title=f"tópico {position}", position=position)

    titles = [topic.title for topic in Topic.objects.with_taught_at()]

    assert titles == ["tópico 1", "tópico 2", "tópico 3"]


@DATABASES
def test_a_taught_topic_and_its_area_cannot_be_deleted() -> None:
    area = create_area()
    topic = create_topic(area)
    create_lesson_row(topic)

    with pytest.raises(ProtectedError):
        topic.delete()
    with pytest.raises(ProtectedError):
        area.delete()

    assert Topic.objects.filter(pk=topic.pk).exists()


@DATABASES
def test_an_area_takes_its_untaught_topics_with_it() -> None:
    area = create_area()
    create_topic(area)

    area.delete()

    assert not Topic.objects.exists()


@DATABASES
def test_a_topic_is_taught_on_its_latest_sent_lesson_only() -> None:
    area = create_area()
    taught = create_topic(area, title="taught", position=1)
    tried = create_topic(area, title="tried", position=2)
    create_topic(area, title="new", position=3)
    create_lesson_row(taught, started_at=datetime(2026, 11, 10, 9, 40, tzinfo=UTC))
    create_lesson_row(taught, started_at=datetime(2026, 11, 12, 9, 40, tzinfo=UTC))
    create_lesson_row(
        taught,
        status=Episode.Status.FAILED,
        started_at=datetime(2026, 11, 13, 9, 40, tzinfo=UTC),
    )
    create_lesson_row(tried, status=Episode.Status.FAILED)
    create_lesson_row(tried, status=Episode.Status.NOT_SENT)
    create_lesson_row(tried, kind=Episode.Kind.NEWS)

    taught_at = {
        topic.title: getattr(topic, "taught_at")
        for topic in Topic.objects.with_taught_at()
    }

    assert taught_at == {
        "taught": datetime(2026, 11, 12, 9, 40, tzinfo=UTC),
        "tried": None,
        "new": None,
    }


def squash_state_episode() -> Any:
    """The Episode model as the squashed migration left it: the code still on main."""
    state = MigrationLoader(None, ignore_no_migrations=True).project_state(SQUASH)
    return state.apps.get_model("news_podcast", "Episode")


def migrate_to(targets: list[tuple[str, str]]) -> None:
    MigrationExecutor(connections["news_podcast_db"]).migrate(targets)


def episode_columns() -> list[str]:
    connection = connections["news_podcast_db"]
    with connection.cursor() as cursor:
        table = connection.introspection.get_table_description(
            cursor, "news_podcast_episode"
        )
    return [column.name for column in table]


# transaction=True: migrating runs schema changes, which a test wrapped in a
# transaction can't do on every database.
@pytest.mark.django_db(databases=["default", "news_podcast_db"], transaction=True)
def test_the_migration_gives_old_rows_the_news_kind_and_no_lesson_fields() -> None:
    try:
        migrate_to([SQUASH])
        assert "kind" not in episode_columns()
        old = squash_state_episode().objects.create(
            started_at=datetime(2026, 11, 12, 9, 40, tzinfo=UTC),
            status="sent",
            cost_usd=0.1,
        )
    finally:
        latest = MigrationLoader(None, ignore_no_migrations=True).graph.leaf_nodes(
            "news_podcast"
        )
        migrate_to(latest)

    row = Episode.objects.get(pk=old.pk)

    assert (row.kind, row.topic_id, row.story_title, row.pages) == (
        "news",
        None,
        "",
        [],
    )


@DATABASES
def test_main_s_code_still_saves_rows_after_the_migration() -> None:
    old = squash_state_episode().objects.create(
        started_at=datetime(2026, 11, 14, 9, 40, tzinfo=UTC),
        status="sent",
        cost_usd=0.1,
    )

    row = Episode.objects.get(pk=old.pk)

    assert (row.kind, row.story_title, row.pages) == ("news", "", [])


def test_the_lesson_factory_builds_a_complete_row_that_passes_the_admin_checks() -> (
    None
):
    editable = {
        field.name
        for field in LessonSettings._meta.concrete_fields
        if field.editable and not field.primary_key
    }

    assert set(LESSON_SETTINGS) == editable
    build_lesson_settings().full_clean()


def test_no_lesson_setting_has_a_default() -> None:
    fields = LessonSettings._meta.concrete_fields

    assert [field.name for field in fields if field.has_default()] == []


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        ({"min_minutes": 0}, "min_minutes"),
        ({"max_minutes": 10}, "max_minutes"),
        ({"min_minutes": 8, "max_minutes": 7}, "max_minutes"),
        ({"voice_input_price": -1}, "voice_input_price"),
        ({"voice_output_price": -1}, "voice_output_price"),
    ],
)
def test_invalid_lesson_settings_say_what_is_wrong(
    changes: dict[str, Any], field: str
) -> None:
    with pytest.raises(ValidationError) as caught:
        build_lesson_settings(**changes).full_clean()

    assert field in caught.value.message_dict


def test_a_lesson_lasts_from_1_to_9_minutes() -> None:
    build_lesson_settings(min_minutes=1, max_minutes=9).full_clean()


@pytest.mark.parametrize("field", ["min_minutes", "max_minutes"])
def test_an_empty_lesson_minute_is_named_instead_of_crashing_clean(field: str) -> None:
    with pytest.raises(ValidationError) as caught:
        build_lesson_settings(**{field: None}).full_clean()

    assert list(caught.value.message_dict) == [field]


@pytest.mark.parametrize(("field", "fields"), list(LESSON_PROMPT_FIELDS.items()))
@pytest.mark.parametrize("bad", ["Oi, {ouvinte}!", "Hoje é {today:%d}.", "Uma { só"])
def test_a_lesson_prompt_refuses_what_the_lesson_does_not_fill(
    field: str, fields: tuple[str, ...], bad: str
) -> None:
    with pytest.raises(ValidationError) as caught:
        build_lesson_settings(**{field: bad}).full_clean()

    assert caught.value.message_dict[field] == [placeholder_error(bad, fields)]


@pytest.mark.parametrize(("field", "fields"), list(LESSON_PROMPT_FIELDS.items()))
def test_a_lesson_prompt_may_use_its_placeholders_and_doubled_braces(
    field: str, fields: tuple[str, ...]
) -> None:
    prompt = " ".join(f"{{{name}}}" for name in fields) + " {{literal}}"

    build_lesson_settings(**{field: prompt}).full_clean()


@pytest.mark.parametrize("name", ["openai:gpt-4o-mini-tts", "tts-1"])
def test_the_lesson_voice_needs_a_voice_provider(name: str) -> None:
    with pytest.raises(ValidationError) as caught:
        build_lesson_settings(voice_model=name).full_clean()

    assert "voice_model" in caught.value.message_dict


@pytest.mark.parametrize(
    "name", ["gemini-3.8-flash-tts", "google_genai:gemini-3.8-flash-tts"]
)
def test_the_lesson_voice_is_a_bare_gemini_name_or_provider_model(name: str) -> None:
    build_lesson_settings(voice_model=name).full_clean()


def test_the_lesson_prices_key_the_voice_model_as_saved() -> None:
    row = build_lesson_settings(
        voice_model="google_genai:gemini-3.8-flash-tts",
        voice_input_price=0.5,
        voice_output_price=9.0,
    )

    assert row.prices() == {"google_genai:gemini-3.8-flash-tts": ModelPrice(0.5, 9.0)}


@DATABASES
def test_without_a_lesson_row_load_says_to_run_the_seed_and_creates_none() -> None:
    with pytest.raises(SettingsMissing, match="seed_news_podcast"):
        LessonSettings.load()

    assert not LessonSettings.objects.exists()

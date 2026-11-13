from typing import Any

import pytest
from django.core.exceptions import ValidationError

from news_podcast.api.episode import config
from news_podcast.api.episode.schemas import EpisodeOptions
from news_podcast.models import STARTING_VALUES, Feed, PodcastSettings

DATABASES = pytest.mark.django_db(databases=["default", "news_podcast_db"])


def test_the_settings_start_with_the_values_in_the_code() -> None:
    podcast_settings = PodcastSettings()

    podcast_settings.full_clean()
    assert podcast_settings.episode_options() == EpisodeOptions(12, 18, 1.0)
    assert podcast_settings.text_models() == [
        config.TEXT_MODEL,
        config.TEXT_FALLBACK_MODEL,
    ]
    assert podcast_settings.prices() == {
        config.TEXT_MODEL: config.TEXT_MODEL_PRICE,
        config.TEXT_FALLBACK_MODEL: config.TEXT_FALLBACK_MODEL_PRICE,
        config.TTS_MODEL: config.TTS_MODEL_PRICE,
    }


def test_the_starting_values_stay_out_of_the_migrations() -> None:
    # A migration records each field's default, so a text there would need a new
    # migration whenever it changes in the code; a function doesn't.
    for field in PodcastSettings._meta.concrete_fields:
        if field.has_default() and not isinstance(field.default, bool):
            assert callable(field.default), field.name

    podcast_settings = PodcastSettings()
    for name, value in STARTING_VALUES.items():
        assert getattr(podcast_settings, name) == value, name


def test_without_a_fallback_only_the_text_model_writes() -> None:
    podcast_settings = PodcastSettings(fallback_model="")

    assert podcast_settings.text_models() == [config.TEXT_MODEL]
    assert "" not in podcast_settings.prices()


@pytest.mark.parametrize(
    ("values", "field", "message"),
    [
        ({"min_minutes": 3}, "min_minutes", "greater than or equal to 5"),
        ({"min_minutes": 18, "max_minutes": 12}, "max_minutes", "less than the min"),
        ({"speech_speed": 0.25}, "speech_speed", "greater than or equal to 0.5"),
        ({"speech_speed": 2.0}, "max_minutes", "36 minutes of speech"),
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
        PodcastSettings(**values).full_clean()

    assert message in " ".join(caught.value.message_dict[field])


def test_a_prompt_may_use_its_placeholders_and_doubled_braces() -> None:
    PodcastSettings(
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
        PodcastSettings(**{field: name}).full_clean()

    message = " ".join(caught.value.message_dict[field])
    assert "google_genai" in message
    assert "openai" in message


@pytest.mark.parametrize(
    "name",
    ["gemini-3.8-flash", "google_genai:gemini-3.8-flash", "openai:gpt-4.1-mini"],
)
def test_a_text_model_is_a_bare_gemini_name_or_provider_model(name: str) -> None:
    PodcastSettings(text_model=name, fallback_model=name).full_clean()


def test_the_fallback_model_may_be_empty() -> None:
    PodcastSettings(fallback_model="").full_clean()


@DATABASES
def test_the_feed_list_starts_with_the_one_in_the_code() -> None:
    sources = Feed.sources()

    assert {(s.outlet, s.section, s.url) for s in sources} == set(config.STARTING_FEEDS)
    icl = next(source for source in sources if source.outlet == "ICL Notícias")
    assert icl.via_google_news


@DATABASES
def test_feeds_are_read_in_section_order() -> None:
    Feed.start_if_empty()
    Feed.objects.create(
        outlet="Valor", section=Feed.Section.ECONOMIA, url="https://valor.example/rss"
    )

    sections = [source.section for source in Feed.sources()]

    # Of a headline in two feeds of one outlet, the first feed's copy stays.
    assert sections == sorted(sections)


@DATABASES
def test_feeds_turned_off_are_not_read_and_the_list_does_not_start_again() -> None:
    Feed.sources()
    Feed.objects.update(active=False)

    assert Feed.sources() == []
    assert Feed.objects.count() == len(config.STARTING_FEEDS)

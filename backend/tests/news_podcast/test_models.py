from typing import Any

import pytest
from django.core.exceptions import ValidationError

from news_podcast.models import Feed, PodcastSettings, SettingsMissing
from tests.news_podcast.factories import SETTINGS, build_settings

DATABASES = pytest.mark.django_db(databases=["default", "news_podcast_db"])


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

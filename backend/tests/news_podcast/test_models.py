from typing import Any

import pytest
from django.core.exceptions import ValidationError

from news_podcast.api.episode import config
from news_podcast.api.episode.schemas import EpisodeOptions
from news_podcast.models import STARTING_VALUES, PodcastSettings


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

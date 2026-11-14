from typing import Any

from news_podcast.models import PodcastSettings

# A complete settings row with short values that pass clean(). The model names are
# bare and distinct, so the fake models, the usages and the prices all key them the
# same way, and only GEMINI_API_KEY is needed.
SETTINGS: dict[str, Any] = {
    "paused": False,
    "min_minutes": 12,
    "max_minutes": 18,
    "speech_speed": 1.0,
    "text_model": "gemini-text",
    "text_input_price": 0.75,
    "text_output_price": 3.75,
    "fallback_model": "gemini-fallback",
    "fallback_input_price": 0.5,
    "fallback_output_price": 2.0,
    "voice_model": "gemini-voice",
    "voice_input_price": 0.5,
    "voice_output_price": 6.0,
    "selection_prompt": (
        "Escolha de {min_stories} a {max_stories} histórias para {min_minutes} a "
        "{max_minutes} minutos."
    ),
    "script_prompt": "Roteiro de {podcast_name}: {min_words} a {max_words} palavras.",
    "expand_prompt": "Tem {words}; escreva de {min_words} a {max_words}: {script}",
    "voice_style": "Calma.",
    "headline_voice_style": "Firme.",
}


def build_settings(**changes: Any) -> PodcastSettings:
    """An unsaved row, for tests with no database."""
    return PodcastSettings(**{**SETTINGS, **changes})


def create_settings(**changes: Any) -> PodcastSettings:
    return PodcastSettings.objects.create(**{**SETTINGS, **changes})

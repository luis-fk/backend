from datetime import UTC, datetime
from typing import Any

from news_podcast.models import Area, Episode, LessonSettings, PodcastSettings, Topic

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


# A complete lesson settings row with short values that pass clean(); each prompt
# uses every placeholder of its tuple.
LESSON_SETTINGS: dict[str, Any] = {
    "min_minutes": 6,
    "max_minutes": 9,
    "voice_model": "gemini-lesson-voice",
    "voice_input_price": 0.5,
    "voice_output_price": 9.0,
    "choice_prompt": "Hoje é {today}. Escolha um tema só se ele se ligar à notícia.",
    "pick_prompt": "Hoje é {today}. Até {max_pages} páginas sobre {topic}, de {area}.",
    "script_prompt": (
        "{host_a} explica e {host_b} pergunta. Hoje é {today}: {topic}, de {area}, "
        "de {min_words} a {max_words} palavras. Resumo enviado: {news_sent}."
    ),
    "review_prompt": "Hoje é {today}. Revise a aula sobre {topic} contra as páginas.",
    "voice_style": "Calma e didática.",
}


def build_settings(**changes: Any) -> PodcastSettings:
    """An unsaved row, for tests with no database."""
    return PodcastSettings(**{**SETTINGS, **changes})


def create_settings(**changes: Any) -> PodcastSettings:
    return PodcastSettings.objects.create(**{**SETTINGS, **changes})


def build_lesson_settings(**changes: Any) -> LessonSettings:
    """An unsaved row, for tests with no database."""
    return LessonSettings(**{**LESSON_SETTINGS, **changes})


def create_lesson_settings(**changes: Any) -> LessonSettings:
    return LessonSettings.objects.create(**{**LESSON_SETTINGS, **changes})


def create_area(**changes: Any) -> Area:
    return Area.objects.create(**{"name": "Justiça", "position": 1, **changes})


def create_topic(area: Area, **changes: Any) -> Topic:
    values = {"position": 1, "title": "O STF: o que julga", "active": True}
    return Topic.objects.create(area=area, **{**values, **changes})


def create_lesson_row(topic: Topic | None = None, **changes: Any) -> Episode:
    """A lesson in the history, sent unless changes say otherwise."""
    values = {
        "kind": Episode.Kind.LESSON,
        "status": Episode.Status.SENT,
        "started_at": datetime(2026, 11, 13, 9, 40, tzinfo=UTC),
        "cost_usd": 0,
    }
    return Episode.objects.create(topic=topic, **{**values, **changes})

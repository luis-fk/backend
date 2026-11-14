from datetime import datetime
from pathlib import Path
from typing import Literal, NamedTuple

from pydantic import BaseModel, ConfigDict, Field

from news_podcast.api.core.schemas import ModelPrice


class EpisodeOptions(NamedTuple):
    min_minutes: int
    max_minutes: int
    speech_speed: float


class FeedSource(BaseModel):
    outlet: str
    section: str
    url: str
    via_google_news: bool


class NewsItem(BaseModel):
    id: str
    outlet: str
    section: str
    title: str
    summary: str
    link: str
    published_at: datetime | None
    content: str = ""


# Gemini reads the field descriptions of SelectedStory, so they are in Portuguese,
# like the prompts.
class SelectedStory(BaseModel):
    model_config = ConfigDict(
        coerce_numbers_to_str=True, json_schema_serialization_defaults_required=True
    )

    title: str = Field(description="Título curto da história.")
    category: Literal["politica", "economia", "mundo", "geral"] = "geral"
    minutes: float = Field(
        default=1.0, gt=0, description="Minutos de fala desta história."
    )
    angle: str = Field(
        default="",
        description="Em uma frase, o que o ouvinte precisa entender da história.",
    )
    item_ids: list[str] = Field(
        description="Os ids de todas as manchetes deste fato, de veículos "
        "diferentes quando houver."
    )


class StorySelection(BaseModel):
    stories: list[SelectedStory]


class SourceText(BaseModel):
    outlet: str
    title: str
    text: str


class StoryBrief(BaseModel):
    title: str
    category: str
    minutes: float
    angle: str
    sources: list[SourceText]
    other_headlines: list[SourceText] = []


class EpisodeSettings(BaseModel):
    """The admin's settings for one run, read by run.py outside the event loop, so
    the service never touches the ORM."""

    model_config = ConfigDict(frozen=True)

    options: EpisodeOptions
    text_models: tuple[str, ...]
    voice_model: str
    selection_prompt: str
    script_prompt: str
    expand_prompt: str
    voice_style: str
    headline_voice_style: str
    prices: dict[str, ModelPrice]


class EpisodeReport(BaseModel):
    audio_path: Path
    duration_seconds: float
    caption: str
    script_words: int

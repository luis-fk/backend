from datetime import datetime
from pathlib import Path
from typing import Literal, NamedTuple

from pydantic import BaseModel, ConfigDict, Field


class EpisodeOptions(NamedTuple):
    min_minutes: int
    max_minutes: int
    speech_speed: float


class Host(NamedTuple):
    name: str
    speaker_id: str
    gemini_voice: str


class ModelPrice(NamedTuple):
    input_per_million: float
    output_per_million: float


class TelegramChat(NamedTuple):
    id: str
    name: str
    is_group: bool


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


# Gemini reads the field descriptions of SelectedStory and Turn, so they are in
# Portuguese, like the prompts.
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


class Turn(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)

    speaker: str = Field(description="Quem fala: um dos dois apresentadores.")
    text: str = Field(description="O que a pessoa diz.")
    headline: bool = Field(
        default=False,
        description="true só nas manchetes da escalada, na abertura do episódio.",
    )


class Script(BaseModel):
    turns: list[Turn]


class Usage(BaseModel):
    step: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0


class EpisodeReport(BaseModel):
    audio_path: Path
    duration_seconds: float
    caption: str

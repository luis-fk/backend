from datetime import datetime
from pathlib import Path
from typing import NamedTuple

from pydantic import BaseModel, ConfigDict, Field


class Host(NamedTuple):
    name: str
    speaker_id: str
    gemini_voice: str


class ModelPrice(NamedTuple):
    input_per_million: float
    output_per_million: float


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


class SelectedStory(BaseModel):
    model_config = ConfigDict(coerce_numbers_to_str=True)

    title: str
    category: str = "geral"
    minutes: float = Field(default=1.0, gt=0)
    angle: str = ""
    item_ids: list[str]


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
    speaker: str
    text: str
    headline: bool = False


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

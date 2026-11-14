from collections.abc import Mapping
from typing import NamedTuple

from pydantic import BaseModel, ConfigDict, Field


class Host(NamedTuple):
    name: str
    speaker_id: str
    # The host's voice in each voice provider, by the provider's name.
    voices: Mapping[str, str]


class ModelPrice(NamedTuple):
    input_per_million: float
    output_per_million: float


class NewsStory(NamedTuple):
    """A story the day's selection chose, as the lesson reads it."""

    title: str
    category: str
    angle: str


class TelegramChat(NamedTuple):
    id: str
    name: str
    is_group: bool


# Gemini reads the field descriptions of Turn, so they are in Portuguese, like the
# prompts.
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

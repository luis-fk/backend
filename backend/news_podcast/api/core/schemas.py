from typing import NamedTuple

from pydantic import BaseModel, ConfigDict, Field


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

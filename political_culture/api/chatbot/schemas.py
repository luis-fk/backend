from enum import Enum

from langgraph.graph import MessagesState
from pydantic import BaseModel, Field


class SquadState(MessagesState):
    input: str
    user_id: int
    title: str
    author: str
    content_description: str
    word_count: list[tuple[str, int]]
    response: str
    memory: str
    route: str


class ChatInfo(BaseModel):
    info: str = Field(
        ..., description="Relevant details about the user and the conversation so far."
    )


class Routes(Enum):
    CHAT = "chat"
    ANALYSIS = "analysis"


class Routing(BaseModel):
    route: Routes = Field(
        ...,
        description="Redirect to the chat agent if the message is a general "
        "question or a conversational topic or redirect to the text analysis "
        "if the user submitted a text.",
    )

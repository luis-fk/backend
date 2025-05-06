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


class ChatInfo(BaseModel):
    info: str = Field(
        ..., description="Relevant details about the user and the conversation so far."
    )

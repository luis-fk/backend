from typing import ClassVar, Literal

from langgraph.graph import MessagesState
from pydantic import BaseModel, Field


class Routing(BaseModel):
    route_description: ClassVar = (
        "Answer the user's question to the best of your ability. "
        "Redirect to the web search agent if requested. "
        "End the conversation after the user question has been asnwered."
    )
    route: Literal["continue", "web_search"] = Field(description=route_description)


class ChatInfo(BaseModel):
    info: str = Field(
        description="Relevant details about the user and the conversation so far."
    )


class SquadState(MessagesState):
    route: str
    memory: dict[str, str]

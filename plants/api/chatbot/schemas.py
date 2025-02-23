from typing import ClassVar, Literal

from langgraph.graph import MessagesState
from pydantic import BaseModel, Field



class Routing(BaseModel):
    route_description: ClassVar = (
        "Redirect to the web search agent if requested or the question "
        "asked is not something you can answer yourself and would warrant "
        "a web search. Otherwise, continue the conversation."
    )
    route: Literal["continue", "tools_agent"] = Field(..., description=route_description)


class ChatInfo(BaseModel):
    info: str = Field(
        ..., description="Relevant details about the user and the conversation so far."
    )


class SquadState(MessagesState):
    user_id: int
    route: str
    memory: str


class LLMAnswerSchema(BaseModel):
    message: str = Field(..., description="The response to the user's question.")
    reasoning: str = Field(
        ...,
        description="The reasoning behind the response in a clear and concise manner.",
    )


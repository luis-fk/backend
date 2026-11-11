from typing import ClassVar, Literal

from langgraph.graph import MessagesState
from pydantic import BaseModel, Field


class Routing(BaseModel):
    route_description: ClassVar = (
        "Redirect to the tools agent if a web search is requested, if the question "
        "asked is not something you can answer yourself and would warrant a web "
        "search, or if it is about the person's own plants or their sensor "
        "readings (soil moisture, air humidity, temperature, trends, when they were "
        "measured). Otherwise, continue the conversation."
    )
    route: Literal["continue", "tools_agent"] = Field(
        ..., description=route_description
    )


class ChatInfo(BaseModel):
    info: str = Field(
        ..., description="Relevant details about the user and the conversation so far."
    )


class SquadState(MessagesState):
    user_id: int
    route: str
    memory: str
    # How many times the model has answered from tool results in this answer.
    tool_rounds: int


class LLMAnswerSchema(BaseModel):
    reasoning: str = Field(
        ...,
        description="The reasoning behind the response in a clear and concise manner.",
    )
    message: str = Field(..., description="The response to the user's question.")

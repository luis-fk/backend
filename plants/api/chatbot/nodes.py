import logging
from typing import cast

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from plants.api.chatbot.agents import (
    call_chatbot_agent,
    call_router_agent,
    call_tools_agent,
    call_user_info_agent,
)
from plants.api.chatbot.schemas import SquadState
from plants.models import ChatHistory, UserMemory


def route_picker(state: SquadState) -> str:
    logging.info(f"Routing to {state['route']}")

    if state["route"] in ["tools_agent", "continue"]:
        return state["route"]
    else:
        raise ValueError(
            f"Invalid route '{state['route']}'. Supported routes are 'tools_agent' and 'continue'."
        )


def wrap_up(state: SquadState) -> None:
    user_id = state["user_id"]

    logging.info(f"Wrapping up user {user_id}, storing memory and chat history")

    UserMemory.objects.update_or_create(
        user_id=user_id,
        defaults={"user_id": user_id, "memory": state["memory"]},
    )

    human_response = str(state["messages"][-2].content)
    ChatHistory.objects.create(
        user_id=user_id,
        message=human_response,
        role="human",
    )

    llm_response = str(state["messages"][-1].content)
    ChatHistory.objects.create(
        user_id=user_id,
        message=llm_response,
        role="ai",
    )


def update_memory(state: SquadState) -> SquadState:
    logging.info("Updating memory for user")

    messages: list[BaseMessage] = cast(list[BaseMessage], state["messages"])
    llm_response = call_user_info_agent(messages)

    return {
        **state,
        "memory": llm_response.info,
    }


def router(state: SquadState) -> SquadState:
    logging.info("Initiating routing verification for user")

    lastest_message: HumanMessage = cast(HumanMessage, state["messages"][-1])

    response = call_router_agent(message=lastest_message)
    return {
        **state,
        "route": response.route,
    }


def call_agent(state: SquadState) -> SquadState:
    logging.info("Calling agent for user")

    memory: str = state["memory"] if state["memory"] else ""
    messages: list[BaseMessage] = cast(list[BaseMessage], state["messages"])

    llm_response = call_chatbot_agent(messages=messages, memory=memory)

    ai_message = AIMessage(content=llm_response.message)

    return {**state, "messages": state["messages"] + [ai_message]}


def tools_agent(state: SquadState) -> SquadState:
    pass
    logging.info("Calling web search agent for user")

    latest_message: HumanMessage = cast(HumanMessage, state["messages"][-1])
    user_memory: str = state["memory"]

    response = call_tools_agent(message=latest_message, memory=user_memory)

    return {**state, "messages": [HumanMessage(content=response)]}

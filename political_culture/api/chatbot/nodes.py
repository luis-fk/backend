import logging
from typing import cast

from langchain_core.messages import HumanMessage

from political_culture.api.chatbot.agents import (
    call_router_agent,
    call_user_info_agent,
    text_analyist_agent,
)
from political_culture.api.chatbot.schemas import Routes, SquadState
from political_culture.api.chatbot.utils import clean_html
from political_culture.api.word_counter.service import add_text, add_text_word_count
from political_culture.models import ChatHistory, UserMemory


def router(state: SquadState) -> SquadState:
    logging.info("Initiating routing verification for user")

    lastest_message: HumanMessage = cast(HumanMessage, state["input"])

    response = call_router_agent(message=lastest_message)

    return {
        **state,
        "route": response.route,
    }


def route_picker(state: SquadState) -> Routes:
    logging.info(f"Routing to {state['route']}")

    if state["route"] in [Routes.CHAT, Routes.ANALYSIS]:
        return state["route"]
    else:
        raise ValueError(
            f"Invalid route '{state['route']}'. Supported routes are {Routes.CHAT} and {Routes.ANALYSIS}."
        )


def general_chat(state: SquadState) -> SquadState:
    logging.info("Starting general chat")

    return state


def text_info_extraction(state: SquadState) -> SquadState:
    logging.info("Starting text info extraction")

    text = state["input"]
    user_id = state["user_id"]

    text_db = add_text(text, user_id, user_submitted_text=True)

    logging.info("Getting word frequency and total word count")

    word_count = add_text_word_count(text_db)

    logging.info("Data created successfully")

    return {
        **state,
        "word_count": word_count.word_frequencies,
        "content_description": text_db.content_description,
        "title": text_db.title or "unknown",
        "author": text_db.author or "unknown",
    }


def text_analysis(state: SquadState) -> SquadState:
    logging.info("Starting text analysis")

    input = (
        f"Title: {state['title']} \nAuthor: {state['author']}"
        f"\n\nSummary: {state['content_description']} \n\nWord Count: {state['word_count']}"
    )

    response = text_analyist_agent(input)

    return {**state, "response": response}


def wrap_up(state: SquadState) -> None:
    human_message: str = state["input"]

    updated_user_memory = call_user_info_agent(human_message)

    user_id = state["user_id"]

    UserMemory.objects.update_or_create(
        user_id=user_id,
        defaults={"user_id": user_id, "memory": updated_user_memory.info},
    )

    logging.info(f"Wrapping up user {user_id}, storing memory and chat history")

    ChatHistory.objects.create(
        user_id=user_id,
        message=human_message,
        role="human",
    )

    llm_response = str(state["response"])

    cleaned_llm_response = clean_html(llm_response)

    ChatHistory.objects.create(
        user_id=user_id,
        message=cleaned_llm_response,
        role="ai",
    )

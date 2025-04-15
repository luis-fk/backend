import logging

from political_culture.api.chatbot.agents import (
    call_title_and_author_extractor_agent,
)
from political_culture.api.chatbot.schemas import SquadState
from political_culture.models import Texts


def text_info_extraction(state: SquadState) -> SquadState:
    logging.info("Starting text info extraction")

    text = state["text"]
    user_id = state["user_id"]

    text_data = call_title_and_author_extractor_agent(text)

    title = text_data.title
    author = text_data.author

    logging.info("Adding text to the database")

    Texts.objects.create(
        user_id=user_id,
        text=text,
        title=title,
        author=author,
    )

    return state

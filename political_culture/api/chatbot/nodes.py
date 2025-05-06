import logging

from political_culture.api.chatbot.agents import text_analyist_agent
from political_culture.api.chatbot.schemas import SquadState
from political_culture.api.word_counter.service import add_text, add_text_word_count


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

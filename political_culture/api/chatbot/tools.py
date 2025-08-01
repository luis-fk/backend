from typing import Optional, cast

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
)
from langchain_core.tools import tool

from political_culture.models import (
    ChatHistory,
    IdeologiesDefinition,
    Texts,
    TextWordCount,
    UserMemory,
)


@tool
def get_all_texts_info() -> list[
    tuple[int, Optional[str], Optional[str], Optional[str], Optional[str]]
]:
    """
    Return a list of all titles, authors and context summaries from the database.
    The list is a list of tuples, where each tuple contains the id, title,
    author and context summary for each text.
    """
    texts_info = Texts.objects.filter(user_submitted_text=False).values_list(
        "id", "title", "ideology", "author", "content_description"
    )

    return list(texts_info)


@tool
def get_text_word_count_by_id(text_id: int) -> TextWordCount | None:
    """
    Return a TextWordCount object for a given text_id.

    Args:
        text_id: The id of the text to retrieve the word count for.

    Returns:
        A TextWordCount object with the words and their frequencies,
        or None if no object is found.
    """
    return (
        TextWordCount.objects.filter(text_id=text_id)
        .values_list("word_frequencies", flat=True)
        .first()
    )


@tool
def get_recent_chat_history(user_id: int) -> list[BaseMessage] | None:
    """
    Return a list of recent chat history messages for a given user_id.

    The list contains the 5 most recent human messages and their corresponding AI
    responses. The list is ordered in reverse chronological order (newest messages first).

    Args:
        user_id: The id of the user to retrieve the chat history for.

    Returns:
        A list of BaseMessage objects, or None if no messages are found.
    """
    human_messages = ChatHistory.objects.filter(user_id=user_id, role="human").order_by(
        "id"
    )[:5]

    ai_messages = ChatHistory.objects.filter(user_id=user_id, role="ai").order_by("id")[
        :5
    ]

    chat_history: list[BaseMessage] = []

    for human, ai in zip(human_messages, ai_messages):
        chat_history.append(HumanMessage(content=human.message))
        chat_history.append(AIMessage(content=ai.message))

    return chat_history


@tool
def get_user_memory(user_id: int) -> str | None:
    """
    Retrieve the memory associated with a given user_id.

    Args:
        user_id: The id of the user whose memory is to be retrieved.

    Returns:
        A string representation of the user's memory, or None if no memory is found.
    """

    user_memory = (
        UserMemory.objects.filter(user_id=user_id)
        .values_list("memory", flat=True)
        .first()
    )

    return cast(str, user_memory)


@tool
def get_user_submitted_texts_info(
    user_id: int,
) -> list[tuple[int, Optional[str], Optional[str], Optional[str], Optional[str]]]:
    """
    Return a list of all titles, authors and context summaries from the database.
    The list is a list of tuples, where each tuple contains the id, title,
    author and context summary for each text.
    """
    texts_info = Texts.objects.filter(
        user_submitted_text=True, user_id=user_id
    ).values_list("id", "title", "ideology", "author", "content_description")

    return list(texts_info)


@tool
def get_ideologies() -> list[tuple[int, str]]:
    """
    Retrieve all the ideologies from the database.

    Returns:
        A list of tuples, where each tuple contains the id and name of the ideology.
        If no ideologies are found, None is returned.
    """
    ideologies = IdeologiesDefinition.objects.values_list("id", "ideology")

    return list(ideologies)


@tool
def get_ideology_definition(ideology_id: int) -> str:
    """
    Retrieve the definition of a specific ideology from the database.

    Args:
        ideology_id: The id of the ideology to retrieve the definition for.

    Returns:
        A string containing the definition of the ideology, or None if no definition is found.
    """
    ideologies = (
        IdeologiesDefinition.objects.filter(id=ideology_id)
        .values_list("definition")
        .first()
    )

    return cast(str, ideologies)

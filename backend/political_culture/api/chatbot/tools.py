from typing import Any, NamedTuple, Optional, cast

from django.db.models import Q
from langchain_core.tools import BaseTool, tool

from political_culture.models import (
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
    ideology, author and context summary for each text.
    """
    texts_info = Texts.objects.filter(user_submitted_text=False).values_list(
        "id", "title", "ideology", "author", "content_description"
    )

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
        A string containing the definition of the ideology, or None if not found.
    """
    ideologies = (
        IdeologiesDefinition.objects.filter(id=ideology_id)
        .values_list("definition")
        .first()
    )

    return cast(str, ideologies)


class UserTools(NamedTuple):
    word_count: BaseTool
    submitted_texts: BaseTool
    memory: BaseTool


def user_tools(user_id: int) -> UserTools:
    """The tools that read one user's data, bound to the user of the conversation.
    The model never picks the user, so it can't read another user's data."""

    @tool
    def get_text_word_count_by_id(text_id: int) -> dict[str, Any] | None:
        """
        Return the words and their frequencies for a given text_id.

        Args:
            text_id: The id of the text to retrieve the word count for.

        Returns:
            The words and their frequencies, or None if no text is found.
        """
        # Texts pasted in the chat belong to the user who pasted them.
        visible = Q(text__user_submitted_text=False) | Q(text__user_id=user_id)
        return cast(
            dict[str, Any] | None,
            TextWordCount.objects.filter(visible, text_id=text_id)
            .values_list("word_frequencies", flat=True)
            .first(),
        )

    @tool
    def get_user_submitted_texts_info() -> list[
        tuple[int, Optional[str], Optional[str], Optional[str], Optional[str]]
    ]:
        """
        Return the texts the user pasted in the chat, as a list of tuples with the
        id, title, ideology, author and context summary of each text.
        """
        texts_info = Texts.objects.filter(
            user_submitted_text=True, user_id=user_id
        ).values_list("id", "title", "ideology", "author", "content_description")

        return list(texts_info)

    @tool
    def get_user_memory() -> str | None:
        """
        Retrieve what is known about the user from past conversations.

        Returns:
            The user's memory, or None if there is none yet.
        """
        user_memory = (
            UserMemory.objects.filter(user_id=user_id)
            .values_list("memory", flat=True)
            .first()
        )

        return cast(str | None, user_memory)

    return UserTools(
        get_text_word_count_by_id, get_user_submitted_texts_info, get_user_memory
    )

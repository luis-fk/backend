from typing import Any, NamedTuple, Optional, cast

from django.db.models import Q
from langchain_core.tools import BaseTool, tool
from langchain_openai import OpenAIEmbeddings
from pgvector.django import CosineDistance

from political_culture.api.word_counter.schemas import ChunkSchema
from political_culture.models import (
    IdeologiesDefinition,
    TextChunks,
    Texts,
    TextWordCount,
    UserMemory,
)


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
    library_texts: BaseTool
    search_text: BaseTool
    word_count: BaseTool
    submitted_texts: BaseTool
    memory: BaseTool


def user_tools(user_id: int) -> UserTools:
    """The tools that read one user's data, bound to the user of the conversation.
    The model never picks the user, so it can't read another user's data, and it
    sees only the library texts this user ticked on the Textos page."""
    # Texts pasted in the chat belong to the user who pasted them.
    readable = Q(selected_by__id=user_id) | Q(user_submitted_text=True, user_id=user_id)

    @tool
    def get_all_texts_info() -> list[
        tuple[int, Optional[str], Optional[str], Optional[str], Optional[str]]
    ]:
        """
        Return the library texts the user chose for their analyses, as a list of
        tuples with the id, title, ideology, author and context summary of each text.
        An empty list means the user hasn't chosen any: they tick them on the
        Textos page.
        """
        texts_info = Texts.objects.filter(
            selected_by__id=user_id, user_submitted_text=False
        ).values_list("id", "title", "ideology", "author", "content_description")

        return list(texts_info)

    @tool
    def query_vectors(text_id: int, query: str) -> list[ChunkSchema]:
        """
        Tool to query the best matching chunks of a text based on a query string.

        Args:
            text_id (int): The ID of the text to query.
            query (str): The query string to match against the text.

        Returns:
            list[ChunkSchema]: A list of the best matching chunks, sorted by score.
        """
        query_vector = OpenAIEmbeddings().embed_query(query)

        chunks = (
            TextChunks.objects.filter(
                text_id=text_id, text__in=Texts.objects.filter(readable)
            )
            .annotate(score=CosineDistance("vector", query_vector))
            .order_by("score")[:3]
        )

        return [
            ChunkSchema(id=chunk.id, text=chunk.chunk_text, score=chunk.score)
            for chunk in chunks
        ]

    @tool
    def get_text_word_count_by_id(text_id: int) -> dict[str, Any] | None:
        """
        Return the words and their frequencies for a given text_id.

        Args:
            text_id: The id of the text to retrieve the word count for.

        Returns:
            The words and their frequencies, or None if no text is found.
        """
        return cast(
            dict[str, Any] | None,
            TextWordCount.objects.filter(
                text_id=text_id, text__in=Texts.objects.filter(readable)
            )
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
        get_all_texts_info,
        query_vectors,
        get_text_word_count_by_id,
        get_user_submitted_texts_info,
        get_user_memory,
    )

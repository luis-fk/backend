from typing import Any, NamedTuple, Optional, cast

from django.db.models import Q
from langchain_core.tools import BaseTool, tool
from langchain_openai import OpenAIEmbeddings
from pgvector.django import CosineDistance

from political_culture.api.word_counter.schemas import ChunkSchema, SurroundingText
from political_culture.api.word_counter.service import CHUNK_OVERLAP_CHARS
from political_culture.models import (
    IdeologiesDefinition,
    TextChunks,
    Texts,
    TextWordCount,
    UserMemory,
)

MAX_SURROUNDING_CHUNKS = 2
# A shorter match where two chunks meet is a coincidence, not the chunks' overlap.
MIN_OVERLAP_CHARS = 20


def repeated_overlap(left: str, right: str) -> int:
    """How many characters at the start of right repeat the end of left."""
    longest = min(len(left), len(right), CHUNK_OVERLAP_CHARS)
    for size in range(longest, MIN_OVERLAP_CHARS - 1, -1):
        if left.endswith(right[:size]):
            return size
    return 0


def joined(chunks: list[str]) -> str:
    """The chunks as one text, without what each one repeats of the one before.
    Chunks of different pages repeat nothing and become separate paragraphs."""
    text = ""
    for chunk in chunks:
        overlap = repeated_overlap(text, chunk)
        if overlap:
            text += chunk[overlap:]
        else:
            text = f"{text}\n\n{chunk}" if text else chunk
    return text


def text_around(chunk: str, before: list[str], after: list[str]) -> SurroundingText:
    text_before = joined(before)
    text_before = text_before[: len(text_before) - repeated_overlap(text_before, chunk)]
    text_after = joined([chunk, *after])[len(chunk) :]
    return SurroundingText(before=text_before.strip(), after=text_after.strip())


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
    surrounding_text: BaseTool
    word_count: BaseTool
    submitted_texts: BaseTool
    memory: BaseTool


def user_tools(user_id: int) -> UserTools:
    """The tools that read one user's data, bound to the user of the conversation.
    The model never picks the user, so it can't read another user's data, and it
    sees only the library texts this user ticked on the Textos page."""
    # Texts pasted in the chat belong to the user who pasted them.
    readable = Q(selected_by__id=user_id) | Q(user_submitted_text=True, user_id=user_id)
    # The chunks the search returned in this answer: the only ones whose surrounding
    # text the model may read, so it can't walk through a text by guessing ids.
    found: set[int] = set()

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

        results = [
            ChunkSchema(id=chunk.id, text=chunk.chunk_text, score=chunk.score)
            for chunk in chunks
        ]
        found.update(result.id for result in results)
        return results

    @tool
    def get_surrounding_text(
        chunk_id: int, chunks_before: int = 1, chunks_after: int = 1
    ) -> SurroundingText | None:
        """
        Return the text right before and right after a chunk that query_vectors
        returned, for when the chunk alone lacks context.

        Args:
            chunk_id: The id of a chunk query_vectors returned.
            chunks_before: How many chunks of text before it, from 0 to 2.
            chunks_after: How many chunks of text after it, from 0 to 2.

        Returns:
            The text before and the text after the chunk, or None if query_vectors
            didn't return this chunk.
        """
        if chunk_id not in found:
            return None
        chunk_row = (
            TextChunks.objects.filter(id=chunk_id)
            .values_list("text_id", "chunk_text")
            .first()
        )
        if chunk_row is None:
            return None
        text_id, chunk = chunk_row
        # Chunks are saved in reading order, so within a text their ids follow it;
        # another upload's chunks may take ids in between.
        same_text = TextChunks.objects.filter(text_id=text_id)
        before = same_text.filter(id__lt=chunk_id).order_by("-id")
        after = same_text.filter(id__gt=chunk_id).order_by("id")
        count_before = max(0, min(chunks_before, MAX_SURROUNDING_CHUNKS))
        count_after = max(0, min(chunks_after, MAX_SURROUNDING_CHUNKS))
        texts_before = list(before.values_list("chunk_text", flat=True)[:count_before])
        texts_after = list(after.values_list("chunk_text", flat=True)[:count_after])
        return text_around(
            chunk or "",
            [text or "" for text in reversed(texts_before)],
            [text or "" for text in texts_after],
        )

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
        library_texts=get_all_texts_info,
        search_text=query_vectors,
        surrounding_text=get_surrounding_text,
        word_count=get_text_word_count_by_id,
        submitted_texts=get_user_submitted_texts_info,
        memory=get_user_memory,
    )

from langchain_core.tools import tool
from langchain_openai import OpenAIEmbeddings
from pgvector.django import CosineDistance

from political_culture.api.word_counter.schemas import ChunkSchema
from political_culture.models import TextChunks


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
        TextChunks.objects.filter(text_id=text_id)
        .annotate(score=CosineDistance("vector", query_vector))
        .order_by("score")[:5]
    )

    return [
        ChunkSchema(id=chunk.id, text=chunk.chunk_text, score=chunk.score)
        for chunk in chunks
    ]

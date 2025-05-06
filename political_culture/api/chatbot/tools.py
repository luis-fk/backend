from typing import Optional

from langchain_core.tools import tool

from political_culture.models import Texts, TextWordCount


@tool
def get_all_texts_info() -> list[tuple[int, Optional[str], Optional[str], str]]:
    """
    Return a list of all titles, authors and context summaries from the database.
    The list is a list of tuples, where each tuple contains the id, title,
    author and context summary for each text.
    """
    texts_info = Texts.objects.filter(user_submitted_text=False).values_list(
        "id", "title", "author", "content_description"
    )

    return list(texts_info)


@tool
def get_text_by_id(text_id: int) -> Optional[Texts]:
    """
    Return a Texts object for a given text_id.

    Args:
        text_id: The id of the text to retrieve.

    Returns:
        A Texts object, or None if no object is found.
    """
    return Texts.objects.filter(id=text_id).first()


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
    return TextWordCount.objects.filter(text_id=text_id).first()

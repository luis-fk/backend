import logging
import re
from typing import Any, Callable, Dict, Optional, Type, TypeVar

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from political_culture.api.messages.serializers import ChatHistorySerializer
from political_culture.api.word_counter.service import (
    count_words,
    extract_text_info,
    word_picker,
)
from political_culture.models import ChatHistory, Texts, TextWordCount

T = TypeVar("T")


def singleton(cls: Type[T]) -> Callable[..., T]:
    instances: Dict[Type[T], T] = {}

    def get_instance(*args: Any, **kwargs: Any) -> T:
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]

    return get_instance


def clean_html(html_string: str) -> str:
    return re.sub(r"<[^>]+>", "", html_string)


def add_text(
    text: str, user_id: int, *, user_submitted_text: Optional[bool] = False
) -> Texts:
    text_data = extract_text_info(text)

    title = text_data.title
    author = text_data.author
    content_description = text_data.content_description

    logging.info("Adding text to the database")

    return Texts.objects.create(
        user_id=user_id,
        text=text,
        title=title,
        author=author,
        user_submitted_text=bool(user_submitted_text),
        content_description=content_description,
    )


def add_text_word_count(text_db: Texts) -> TextWordCount:
    word_frequencies, total_word_count = count_words(text_db.text)

    new_word_frequencies = word_picker(word_frequencies, text_db.content_description)

    dict_word_frequencies = {
        word_count.word: word_count.count
        for word_count in new_word_frequencies.words_list
    }

    return TextWordCount.objects.create(
        text=text_db,
        total_word_count=total_word_count,
        word_frequencies=dict_word_frequencies,
    )


def get_recent_chat_history_db(user_id: int) -> list[BaseMessage]:
    """The user's last five exchanges, oldest first."""
    human_messages = list(
        ChatHistory.objects.filter(user_id=user_id, role="human").order_by("-id")[:5]
    )[::-1]
    ai_messages = list(
        ChatHistory.objects.filter(user_id=user_id, role="ai").order_by("-id")[:5]
    )[::-1]

    chat_history: list[BaseMessage] = []

    for human, ai in zip(human_messages, ai_messages):
        chat_history.append(HumanMessage(content=human.message))
        chat_history.append(AIMessage(content=ai.message))

    return chat_history


def wrap_up_get_response(user_id: int) -> dict[str, Any]:
    llm_response = ChatHistory.objects.filter(user_id=user_id, role="ai").last()
    if llm_response:
        return ChatHistorySerializer(llm_response).data
    return {}

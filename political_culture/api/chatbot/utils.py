import logging
import re
from typing import Any, Callable, Dict, Optional, Type, TypeVar

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.prompts import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    SystemMessagePromptTemplate,
)

from political_culture.api.utils import llm_4
from political_culture.api.word_counter.prompts import TEXT_INFO_EXTRACTION_PROMPT
from political_culture.api.word_counter.schemas import TitleAndAuthorSchema
from political_culture.api.word_counter.service import count_words, word_picker
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


def text_info_extractor(text: str) -> TitleAndAuthorSchema:
    instructions_prompt = ChatPromptTemplate.from_messages(
        [
            SystemMessagePromptTemplate.from_template(TEXT_INFO_EXTRACTION_PROMPT),
            HumanMessagePromptTemplate.from_template("{input}"),
        ]
    )

    chain = instructions_prompt | llm_4.with_structured_output(
        schema=TitleAndAuthorSchema, method="json_schema"
    )

    response = chain.invoke({"input": text})

    return TitleAndAuthorSchema.model_validate(response)


def add_text(
    text: str, user_id: int, *, user_submitted_text: Optional[bool] = False
) -> Texts:
    text_data = text_info_extractor(text)

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

    dict_word_frequencies = dict(
        (word_count.word, word_count.count)
        for word_count in new_word_frequencies.words_list
    )

    return TextWordCount.objects.create(
        text=text_db,
        total_word_count=total_word_count,
        word_frequencies=dict_word_frequencies,
    )


def get_recent_chat_history_db(user_id: int) -> list[BaseMessage]:
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

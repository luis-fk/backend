import logging
import re
from collections import Counter
from typing import Optional

from environ import Env
from langchain_core.prompts import (
    AIMessagePromptTemplate,
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    SystemMessagePromptTemplate,
)
from langchain_openai import ChatOpenAI

from political_culture.api.word_counter.prompts import (
    TEXT_INFO_EXTRACTION_PROMPT,
    WORD_EXTRACTION_PROMPT,
)
from political_culture.api.word_counter.schemas import (
    TitleAndAuthorSchema,
    WordFrequencySquema,
)
from political_culture.models import Texts, TextWordCount

env = Env()
Env.read_env()

llm_4 = ChatOpenAI(model="gpt-4o-mini", temperature=0.5)


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


def word_picker(words: list[tuple[str, int]]) -> WordFrequencySquema:
    instructions_prompt = ChatPromptTemplate.from_messages(
        [
            SystemMessagePromptTemplate.from_template(WORD_EXTRACTION_PROMPT),
            AIMessagePromptTemplate.from_template("{input}"),
        ]
    )

    chain = instructions_prompt | llm_4.with_structured_output(
        schema=WordFrequencySquema, method="json_schema"
    )

    response = chain.invoke({"input": words})

    return WordFrequencySquema.model_validate(response)


def count_words(text: str) -> tuple[list[tuple[str, int]], int]:
    all_words = re.findall(r"\w+", text.lower())

    words = [word for word in all_words if len(word) > 2]

    word_counts = Counter(words)

    sorted_word_counts = sorted(
        word_counts.items(), key=lambda item: item[1], reverse=True
    )

    total_word_count = sum(word_counts.values())

    return sorted_word_counts, total_word_count


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

    new_word_frequencies = word_picker(word_frequencies)

    dict_word_frequencies = dict(
        (word_count.word, word_count.count)
        for word_count in new_word_frequencies.words_list
    )

    return TextWordCount.objects.create(
        text=text_db,
        total_word_count=total_word_count,
        word_frequencies=dict_word_frequencies,
    )

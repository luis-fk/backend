import re
from collections import Counter

from environ import Env
from langchain import hub
from langchain_openai import ChatOpenAI

from political_culture.api.word_counter.schemas import TitleAndAuthorSchema

env = Env()
Env.read_env()

llm_4 = ChatOpenAI(model="gpt-4o-mini", temperature=0.5)


def call_title_and_author_extractor_agent(text: str) -> TitleAndAuthorSchema:
    instructions = hub.pull("extract_title_and_author")

    chain = instructions | llm_4.with_structured_output(
        schema=TitleAndAuthorSchema, method="json_schema"
    )

    response = chain.invoke({"input": text})

    return TitleAndAuthorSchema.model_validate(response)


def count_words(text: str, list_size: int) -> tuple[list[tuple[str, int]], int]:
    all_words = re.findall(r"\w+", text.lower())

    words = [word for word in all_words if len(word) > 2]

    word_counts = Counter(words)

    sorted_word_counts = sorted(
        word_counts.items(), key=lambda item: item[1], reverse=True
    )

    total_word_count = sum(word_counts.values())

    return sorted_word_counts[:list_size], total_word_count

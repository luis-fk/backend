import re
from collections import Counter

from environ import Env
from langchain_openai import ChatOpenAI

env = Env()
Env.read_env()

llm_4 = ChatOpenAI(model="gpt-4o-mini", temperature=0.5)


def count_words(text: str, list_size: int) -> tuple[list[tuple[str, int]], int]:
    all_words = re.findall(r"\w+", text.lower())

    words = [word for word in all_words if len(word) > 2]

    word_counts = Counter(words)

    sorted_word_counts = sorted(
        word_counts.items(), key=lambda item: item[1], reverse=True
    )

    total_word_count = sum(word_counts.values())

    return sorted_word_counts[:list_size], total_word_count

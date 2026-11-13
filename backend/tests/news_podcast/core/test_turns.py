import pytest

from news_podcast.api.core.config import (
    HOSTS,
)
from news_podcast.api.core.llm import BadAnswerError
from news_podcast.api.core.schemas import (
    Turn,
)
from news_podcast.api.core.turns import (
    MIN_SCRIPT_TURNS,
    checked_turns,
    chunk_turns,
    clean_turns,
    count_words,
)


def test_clean_turns_fixes_speakers_and_removes_markup() -> None:
    turns = [
        Turn(speaker="Leo", text="**Léo:** Veja em https://g1.globo.com 😀 isso"),
        Turn(speaker="desconhecido", text="Texto normal"),
        Turn(speaker="Bia", text="   "),
    ]

    cleaned = clean_turns(turns, HOSTS)

    assert cleaned == [
        Turn(speaker="Léo", text="Veja em isso"),
        Turn(speaker="Léo", text="Texto normal"),
    ]


def test_chunk_turns_respects_the_word_limit_and_keeps_order() -> None:
    turns = [Turn(speaker="Bia", text="palavra " * 40) for _ in range(5)]

    chunks = chunk_turns(turns, max_words=100)

    assert [len(chunk) for chunk in chunks] == [2, 2, 1]
    assert count_words([turn for chunk in chunks for turn in chunk]) == 200


def test_chunk_turns_splits_a_single_long_turn_by_sentence() -> None:
    long_text = " ".join(["Uma frase com cinco palavras."] * 10)

    chunks = chunk_turns([Turn(speaker="Bia", text=long_text)], max_words=12)

    assert all(count_words(chunk) <= 12 for chunk in chunks)
    assert count_words([turn for chunk in chunks for turn in chunk]) == 50


def test_cleaning_and_chunking_keep_the_headline_mark() -> None:
    turns = [
        Turn(speaker="Bia", text="**Bia:** Juros sobem de novo.", headline=True),
        Turn(speaker="Leo", text="Bom dia! Hoje é sexta-feira."),
    ]

    chunks = chunk_turns(clean_turns(turns, HOSTS), max_words=100)

    assert [turn.headline for chunk in chunks for turn in chunk] == [True, False]


def test_checked_turns_returns_the_cleaned_turns() -> None:
    turns = [
        Turn(speaker="bia", text=f"**Fala {index}**")
        for index in range(MIN_SCRIPT_TURNS)
    ]

    checked = checked_turns(turns, HOSTS)

    assert len(checked) == MIN_SCRIPT_TURNS
    assert (checked[0].speaker, checked[0].text) == ("Bia", "Fala 0")


def test_a_script_left_with_too_few_turns_is_a_bad_answer() -> None:
    turns = [Turn(speaker="Bia", text="Oi")] * (MIN_SCRIPT_TURNS - 1)
    link_only = Turn(speaker="Léo", text="https://exemplo.com.br/materia")

    with pytest.raises(BadAnswerError, match=f"só {MIN_SCRIPT_TURNS - 1} falas"):
        checked_turns([*turns, link_only], HOSTS)

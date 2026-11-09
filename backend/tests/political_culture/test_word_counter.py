from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.runnables import RunnableLambda

from political_culture.api.word_counter import service
from political_culture.api.word_counter.schemas import TitleAndAuthorSchema

INFO = TitleAndAuthorSchema(
    reasoning="The cover names both.",
    title="O Capital",
    author="Karl Marx",
    content_description="Crítica da economia política.",
)


def test_a_short_text_goes_whole() -> None:
    assert service.text_sample("Um texto curto.", ["Um texto curto."]) == (
        "Um texto curto."
    )


def test_a_long_text_goes_as_its_opening_and_passages_from_the_rest() -> None:
    text = "a" * (service.OPENING_CHARS + 1)
    chunks = [f"trecho {n}" for n in range(8)]

    sample = service.text_sample(text, chunks)

    assert sample.split("\n\n[...]\n\n") == [
        "a" * service.OPENING_CHARS,
        "trecho 2",
        "trecho 4",
        "trecho 6",
    ]


def test_the_extraction_reads_the_text_itself(monkeypatch: pytest.MonkeyPatch) -> None:
    received: list[str] = []

    def extract(prompt: Any) -> dict[str, Any]:
        received.append(prompt.to_string())
        return INFO.model_dump()

    class ExtractionModel:
        def with_structured_output(self, **_kwargs: Any) -> RunnableLambda[Any, Any]:
            return RunnableLambda(extract)

    monkeypatch.setattr(service, "llm_4", ExtractionModel())

    info = service.extract_text_info("O CAPITAL\nKarl Marx\n\nCapítulo 1")

    assert info == INFO
    assert "O CAPITAL\nKarl Marx" in received[0]


def test_analysing_again_keeps_the_embeddings_and_redoes_the_rest() -> None:
    text_db = MagicMock(text="O CAPITAL\nKarl Marx")
    text_db.chunks.order_by.return_value.values_list.return_value = ["O CAPITAL"]

    with (
        patch.object(service, "extract_text_info", return_value=INFO) as extract,
        patch.object(service, "TextWordCount") as word_counts,
        patch.object(service, "add_text_word_count") as add_word_count,
    ):
        service.analyse_again(text_db)

    extract.assert_called_once_with("O CAPITAL\nKarl Marx")
    assert (text_db.title, text_db.author) == ("O Capital", "Karl Marx")
    assert text_db.content_description == "Crítica da economia política."
    text_db.save.assert_called_once()
    word_counts.objects.filter.assert_called_once_with(text=text_db)
    word_counts.objects.filter.return_value.delete.assert_called_once()
    add_word_count.assert_called_once_with(text_db)

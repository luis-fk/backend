from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo

from news_podcast.api.episode.config import HOSTS
from news_podcast.api.episode.schemas import (
    NewsItem,
    SelectedStory,
    StorySelection,
    Turn,
)
from news_podcast.api.episode.utils import (
    chunk_turns,
    clean_turns,
    count_words,
    news_window,
    valid_stories,
)

SAO_PAULO = ZoneInfo("America/Sao_Paulo")


def test_manual_window_ends_now() -> None:
    now = datetime(2026, 11, 6, 17, 30, tzinfo=UTC)

    start, end = news_window(now, False, 24, time(6, 0), SAO_PAULO)

    assert end == now
    assert start == datetime(2026, 11, 5, 17, 30, tzinfo=UTC)


def test_scheduled_window_ends_at_the_morning_cutoff() -> None:
    now = datetime(2026, 11, 6, 9, 15, tzinfo=UTC)

    start, end = news_window(now, True, 24, time(6, 0), SAO_PAULO)

    assert end == datetime(2026, 11, 6, 9, 0, tzinfo=UTC)
    assert start == datetime(2026, 11, 5, 9, 0, tzinfo=UTC)


def test_valid_stories_drops_unknown_ids_and_empty_stories() -> None:
    item = NewsItem(
        id="3",
        outlet="g1",
        section="Política",
        title="t",
        summary="",
        link="",
        published_at=None,
    )
    selection = StorySelection(
        stories=[
            SelectedStory(title="ok", item_ids=["[3]", "99", "3"]),
            SelectedStory(title="vazia", item_ids=["42"]),
        ]
    )

    stories = valid_stories(selection, {"3": item}, max_stories=10)

    assert [story.title for story in stories] == ["ok"]
    assert stories[0].item_ids == ["3"]


def test_selected_story_accepts_numeric_ids() -> None:
    story = SelectedStory.model_validate({"title": "x", "item_ids": [12, 48]})

    assert story.item_ids == ["12", "48"]


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

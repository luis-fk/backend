import asyncio
import json
from datetime import datetime
from typing import Any

import httpx
import pytest
from langchain_core.prompts import ChatPromptTemplate
from pytest_django import Settings

from news_podcast.api.core.config import LOCAL_TZ
from news_podcast.api.core.llm import BadAnswerError, TextModels
from news_podcast.api.episode import config, prompts
from news_podcast.api.episode.feeds import format_for_selection
from news_podcast.api.episode.prompts import selection_template
from news_podcast.api.episode.run import episode_settings
from news_podcast.api.episode.schemas import (
    EpisodeOptions,
    NewsItem,
    SelectedStory,
    StorySelection,
)
from news_podcast.api.episode.selection import (
    checked_selection,
    select_stories,
    selection_values,
    valid_stories,
)
from news_podcast.models import PodcastSettings
from tests.news_podcast.fake_models import FakeChatModel, fake_factory

DEFAULT_OPTIONS = EpisodeOptions(12, 18, 1.0)
START = datetime(2026, 11, 6, 6, 0, tzinfo=LOCAL_TZ)
END = datetime(2026, 11, 7, 6, 0, tzinfo=LOCAL_TZ)


def news_item(item_id: str, title: str = "t") -> NewsItem:
    return NewsItem(
        id=item_id,
        outlet="g1",
        section="Política",
        title=title,
        summary="",
        link="",
        published_at=None,
    )


def system_message(template: ChatPromptTemplate, values: dict[str, Any]) -> str:
    return str(template.format_messages(**values)[0].content)


def every_placeholder(fields: tuple[str, ...]) -> str:
    return " ".join(f"{{{field}}}" for field in fields)


def test_valid_stories_drops_unknown_ids_and_empty_stories() -> None:
    selection = StorySelection(
        stories=[
            SelectedStory(title="ok", item_ids=["[3]", "99", "3"]),
            SelectedStory(title="vazia", item_ids=["42"]),
        ]
    )

    stories = valid_stories(selection, {"3": news_item("3")}, max_stories=10)

    assert [story.title for story in stories] == ["ok"]
    assert stories[0].item_ids == ["3"]


def test_selected_story_accepts_numeric_ids() -> None:
    story = SelectedStory.model_validate({"title": "x", "item_ids": [12, 48]})

    assert story.item_ids == ["12", "48"]


def test_a_selection_without_a_valid_story_is_a_bad_answer() -> None:
    check = checked_selection({"3": news_item("3")}, max_stories=10)

    with pytest.raises(BadAnswerError, match="sem notícias válidas"):
        check(StorySelection(stories=[SelectedStory(title="x", item_ids=["42"])]))

    good = StorySelection(stories=[SelectedStory(title="ok", item_ids=["3"])])
    assert [story.title for story in check(good)] == ["ok"]


def test_the_selection_prompt_follows_the_configured_options() -> None:
    options = EpisodeOptions(20, 30, 1.0)
    start = datetime(2026, 11, 6, 20, 0, tzinfo=LOCAL_TZ)
    end = datetime(2026, 11, 7, 20, 0, tzinfo=LOCAL_TZ)

    selection = system_message(
        selection_template(prompts.SELECTION_PROMPT),
        {"headlines": "", **selection_values(options, start, end)},
    )

    assert "em 20 a 30 minutos" in selection
    assert "Escolha de 13 a 20 histórias" in selection


def test_the_selection_fills_every_placeholder_the_admin_accepts() -> None:
    # A placeholder left without a value would raise KeyError.
    selection = system_message(
        selection_template(every_placeholder(prompts.SELECTION_FIELDS)),
        {"headlines": "", **selection_values(DEFAULT_OPTIONS, START, END)},
    )

    assert selection.startswith("12 18 15 8 12 ")


def test_the_headlines_reach_the_model_as_they_are() -> None:
    template = selection_template("Responda {{sem JSON}} em {min_minutes} minutos.")

    system, human = template.format_messages(
        headlines='Ministro diz "{x}" e {y}',
        **selection_values(DEFAULT_OPTIONS, START, END),
    )

    assert system.content == "Responda {sem JSON} em 12 minutos."
    assert human.content == 'Ministro diz "{x}" e {y}'


def test_the_selection_step_returns_the_valid_stories(settings: Settings) -> None:
    settings.GEMINI_API_KEY = "test-key"
    items = [news_item("3", "Juros sobem"), news_item("7", "Chuva no Sul")]
    answer = {
        "stories": [
            {
                "title": "Juros",
                "category": "economia",
                "minutes": 2,
                "angle": "a",
                "item_ids": ["3"],
            },
            {
                "title": "Sem fonte",
                "category": "geral",
                "minutes": 1,
                "angle": "",
                "item_ids": ["99"],
            },
        ]
    }
    asked: list[str] = []
    built: dict[str, FakeChatModel] = {}

    async def scenario() -> list[SelectedStory]:
        async with httpx.AsyncClient() as client:
            text = TextModels(
                [config.TEXT_MODEL],
                [],
                client,
                fake_factory({config.TEXT_MODEL: [json.dumps(answer)]}, asked, built),
            )
            snapshot = episode_settings(PodcastSettings())
            return await select_stories(text, snapshot, items, START, END)

    stories = asyncio.run(scenario())

    assert [story.title for story in stories] == ["Juros"]
    [messages] = built[config.TEXT_MODEL].received
    assert messages[1].content == format_for_selection(items, LOCAL_TZ)

import logging
from collections.abc import Callable, Sequence
from datetime import datetime
from typing import Any

from news_podcast.api.core.config import LOCAL_TZ
from news_podcast.api.core.llm import BadAnswerError, TextModels
from news_podcast.api.episode.config import PREFERRED_OUTLETS
from news_podcast.api.episode.feeds import format_for_selection
from news_podcast.api.episode.messages import local_label
from news_podcast.api.episode.options import story_range, target_minutes
from news_podcast.api.episode.prompts import selection_template
from news_podcast.api.episode.schemas import (
    EpisodeOptions,
    EpisodeSettings,
    NewsItem,
    SelectedStory,
    StorySelection,
)

logger = logging.getLogger(__name__)


async def select_stories(
    text: TextModels,
    settings: EpisodeSettings,
    items: list[NewsItem],
    start: datetime,
    end: datetime,
) -> list[SelectedStory]:
    items_by_id = {item.id: item for item in items}
    _, max_stories = story_range(settings.options)
    stories = await text.ask(
        selection_template(settings.selection_prompt),
        {
            "headlines": format_for_selection(items, LOCAL_TZ),
            **selection_values(settings.options, start, end),
        },
        step="selection",
        schema=StorySelection,
        check=checked_selection(items_by_id, max_stories),
    )
    log_selection(stories, items_by_id)
    return stories


def selection_values(
    options: EpisodeOptions, start: datetime, end: datetime
) -> dict[str, Any]:
    """The values of the selection prompt's placeholders (SELECTION_FIELDS)."""
    min_stories, max_stories = story_range(options)
    return {
        "min_minutes": options.min_minutes,
        "max_minutes": options.max_minutes,
        "target_minutes": round(target_minutes(options)),
        "min_stories": min_stories,
        "max_stories": max_stories,
        "window_start": local_label(start),
        "window_end": local_label(end),
    }


def checked_selection(
    items_by_id: dict[str, NewsItem], max_stories: int
) -> Callable[[StorySelection], list[SelectedStory]]:
    def check(selection: StorySelection) -> list[SelectedStory]:
        stories = valid_stories(selection, items_by_id, max_stories)
        if not stories:
            raise BadAnswerError("a seleção veio sem notícias válidas")
        return stories

    return check


def log_selection(
    stories: Sequence[SelectedStory], items_by_id: dict[str, NewsItem]
) -> None:
    for story in stories:
        outlets = sorted({items_by_id[item_id].outlet for item_id in story.item_ids})
        logger.info(
            f"Story ({story.minutes} min): {story.title} | {', '.join(outlets)}"
        )

    has_preferred = any(
        items_by_id[item_id].outlet in PREFERRED_OUTLETS
        for story in stories
        for item_id in story.item_ids
    )
    if not has_preferred:
        logger.info("No story from the preferred outlets today")


def valid_stories(
    selection: StorySelection, items_by_id: dict[str, NewsItem], max_stories: int
) -> list[SelectedStory]:
    stories: list[SelectedStory] = []
    for story in selection.stories:
        ids = [
            item_id
            for item_id in dict.fromkeys(raw.strip("[] ") for raw in story.item_ids)
            if item_id in items_by_id
        ]
        if ids:
            stories.append(story.model_copy(update={"item_ids": ids}))
    return stories[:max_stories]

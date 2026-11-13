import logging
from collections.abc import Sequence
from datetime import datetime

from news_podcast.api.episode.config import PREFERRED_OUTLETS
from news_podcast.api.episode.messages import local_label
from news_podcast.api.episode.options import story_range, target_minutes
from news_podcast.api.episode.schemas import (
    EpisodeOptions,
    NewsItem,
    SelectedStory,
    StorySelection,
)

logger = logging.getLogger(__name__)


def selection_prompt(
    template: str, options: EpisodeOptions, start: datetime, end: datetime
) -> str:
    min_stories, max_stories = story_range(options)
    return template.format(
        min_minutes=options.min_minutes,
        max_minutes=options.max_minutes,
        target_minutes=round(target_minutes(options)),
        min_stories=min_stories,
        max_stories=max_stories,
        window_start=local_label(start),
        window_end=local_label(end),
    )


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

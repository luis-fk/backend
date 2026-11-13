from news_podcast.api.episode.schemas import (
    NewsItem,
    SelectedStory,
    StorySelection,
)
from news_podcast.api.episode.selection import valid_stories


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

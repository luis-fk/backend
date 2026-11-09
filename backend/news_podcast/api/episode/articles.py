import asyncio
import logging
from urllib.parse import urlparse

import httpx
import trafilatura
from googlenewsdecoder import gnews_decoder_async

from news_podcast.api.episode.config import (
    FEED_CONTENT_MIN_CHARS,
    FULL_TEXT_DOMAINS,
    HEADLINE_SUMMARY_CHARS,
    HTTP_TIMEOUT_SECONDS,
    MAX_OTHER_HEADLINES,
    MAX_SOURCE_CHARS,
    MAX_SOURCES_PER_STORY,
    PREFERRED_OUTLETS,
    USER_AGENT,
)
from news_podcast.api.episode.feeds import GOOGLE_NEWS_HOST
from news_podcast.api.episode.schemas import (
    NewsItem,
    SelectedStory,
    SourceText,
    StoryBrief,
)

logger = logging.getLogger(__name__)

GOOGLE_NEWS_TIMEOUT_SECONDS = 15.0
GOOGLE_NEWS_CONCURRENCY = 4
VIDEO_PATH_SEGMENTS = frozenset({"video", "videos"})


def host_of(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def allows_full_text(url: str) -> bool:
    host = host_of(url)
    return any(
        host == domain or host.endswith(f".{domain}") for domain in FULL_TEXT_DOMAINS
    )


def is_google_news_link(url: str) -> bool:
    return host_of(url) == GOOGLE_NEWS_HOST


def is_video_page(url: str) -> bool:
    """A video page, like sbtnews.sbt.com.br/videos/..., has no text to read."""
    segments = urlparse(url).path.lower().split("/")
    return not VIDEO_PATH_SEGMENTS.isdisjoint(segments)


def pick_items(
    story: SelectedStory, items_by_id: dict[str, NewsItem], resolved: dict[str, str]
) -> list[NewsItem]:
    candidates = [
        items_by_id[item_id] for item_id in story.item_ids if item_id in items_by_id
    ]
    ranked = sorted(candidates, key=_reading_priority)

    picked: list[NewsItem] = []
    outlets: set[str] = set()
    for item in ranked:
        if is_video_page(resolved.get(item.link, item.link)):
            continue
        if item.outlet not in outlets:
            picked.append(item)
            outlets.add(item.outlet)
        if len(picked) == MAX_SOURCES_PER_STORY:
            break
    return picked


def _reading_priority(item: NewsItem) -> int:
    if item.outlet in PREFERRED_OUTLETS:
        return -1
    if len(item.content) >= FEED_CONTENT_MIN_CHARS or allows_full_text(item.link):
        return 0
    if is_google_news_link(item.link):
        return 1
    return 2


async def build_briefs(
    client: httpx.AsyncClient,
    stories: list[SelectedStory],
    items_by_id: dict[str, NewsItem],
) -> list[StoryBrief]:
    # Every candidate's Google News link is decoded before the picking, since only
    # the real address shows a video page, which must not take a reading slot.
    candidates = [
        items_by_id[item_id]
        for story in stories
        for item_id in story.item_ids
        if item_id in items_by_id
    ]
    google_links = list(
        dict.fromkeys(
            item.link for item in candidates if is_google_news_link(item.link)
        )
    )
    resolved = await resolve_google_news_links(google_links)
    picks = [pick_items(story, items_by_id, resolved) for story in stories]

    async def read_story(items: list[NewsItem]) -> list[SourceText]:
        return list(
            await asyncio.gather(
                *[
                    read_source(client, item, resolved.get(item.link, item.link))
                    for item in items
                ]
            )
        )

    sources_per_story = await asyncio.gather(*[read_story(items) for items in picks])

    return [
        StoryBrief(
            title=story.title,
            category=story.category,
            minutes=story.minutes,
            angle=story.angle,
            sources=sources,
            other_headlines=other_headlines(story, picked, items_by_id),
        )
        for story, picked, sources in zip(stories, picks, sources_per_story)
    ]


def other_headlines(
    story: SelectedStory, picked: list[NewsItem], items_by_id: dict[str, NewsItem]
) -> list[SourceText]:
    read_outlets = {item.outlet for item in picked}
    headlines: list[SourceText] = []
    for item_id in story.item_ids:
        item = items_by_id.get(item_id)
        if item is None or item.outlet in read_outlets:
            continue
        read_outlets.add(item.outlet)
        headlines.append(
            SourceText(
                outlet=item.outlet,
                title=item.title,
                text=item.summary[:HEADLINE_SUMMARY_CHARS],
            )
        )
    return headlines[:MAX_OTHER_HEADLINES]


async def resolve_google_news_links(links: list[str]) -> dict[str, str]:
    if not links:
        return {}

    try:
        results = await gnews_decoder_async(
            links,
            timeout=GOOGLE_NEWS_TIMEOUT_SECONDS,
            concurrency=GOOGLE_NEWS_CONCURRENCY,
        )
    except Exception as error:
        logger.warning(f"Google News link decoding failed: {error}")
        return {}

    result_list = results if isinstance(results, list) else [results]
    resolved: dict[str, str] = {}
    for link, result in zip(links, result_list):
        decoded = result.get("decoded_url") if result.get("success") else None
        if isinstance(decoded, str) and decoded:
            resolved[link] = decoded

    logger.info(f"Decoded {len(resolved)} of {len(links)} Google News links")
    return resolved


async def read_source(
    client: httpx.AsyncClient, item: NewsItem, url: str
) -> SourceText:
    text = item.content if len(item.content) >= FEED_CONTENT_MIN_CHARS else ""

    if not text and allows_full_text(url):
        text = await fetch_article_text(client, url)

    if not text:
        text = item.summary or item.title

    return SourceText(
        outlet=item.outlet, title=item.title, text=text[:MAX_SOURCE_CHARS]
    )


async def fetch_article_text(client: httpx.AsyncClient, url: str) -> str:
    try:
        response = await client.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=HTTP_TIMEOUT_SECONDS,
            follow_redirects=True,
        )
        response.raise_for_status()
    except httpx.HTTPError as error:
        logger.warning(f"Article download failed for {url}: {error}")
        return ""

    extracted = await asyncio.to_thread(
        trafilatura.extract,
        response.text,
        url=url,
        include_comments=False,
        include_tables=False,
        favor_precision=True,
    )
    return extracted or ""

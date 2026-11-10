import asyncio
import calendar
import html
import logging
import re
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

import feedparser
import httpx

from news_podcast.api.episode.config import (
    HTTP_TIMEOUT_SECONDS,
    SELECTION_SUMMARY_CHARS,
    UNDATED_ITEMS_PER_FEED,
    USER_AGENT,
)
from news_podcast.api.episode.schemas import FeedSource, NewsItem

logger = logging.getLogger(__name__)

GOOGLE_NEWS_HOST = "news.google.com"
TAG_PATTERN = re.compile(r"<[^>]+>")
SPACE_PATTERN = re.compile(r"\s+")
PUBLISHER_SUFFIX_MAX_WORDS = 5


def clean_text(raw: str) -> str:
    without_tags = TAG_PATTERN.sub(" ", raw)
    return SPACE_PATTERN.sub(" ", html.unescape(without_tags)).strip()


async def fetch_items(
    client: httpx.AsyncClient,
    sources: list[FeedSource],
    start: datetime,
    end: datetime,
) -> list[NewsItem]:
    payloads = await asyncio.gather(
        *[_download_feed(client, source) for source in sources]
    )

    collected: list[NewsItem] = []
    for source, payload in zip(sources, payloads):
        if payload is not None:
            collected.extend(parse_feed(source, payload, start, end))

    return _number_items(_deduplicate(collected))


async def _download_feed(client: httpx.AsyncClient, source: FeedSource) -> bytes | None:
    try:
        response = await client.get(
            source.url,
            headers={"User-Agent": USER_AGENT},
            timeout=HTTP_TIMEOUT_SECONDS,
            follow_redirects=True,
        )
        response.raise_for_status()
    except httpx.HTTPError as error:
        logger.warning(f"Feed {source.outlet} ({source.section}) failed: {error}")
        return None
    return response.content


def parse_feed(
    source: FeedSource, payload: bytes, start: datetime, end: datetime
) -> list[NewsItem]:
    entries: list[Any] = list(feedparser.parse(payload).entries)
    items: list[NewsItem] = []
    undated = 0

    for entry in entries:
        item = _entry_to_item(source, entry)
        if item is None:
            continue
        if item.published_at is None:
            undated += 1
            if undated <= UNDATED_ITEMS_PER_FEED:
                items.append(item)
        elif start <= item.published_at < end:
            items.append(item)

    return items


def _entry_to_item(source: FeedSource, entry: Any) -> NewsItem | None:
    title = clean_text(str(entry.get("title", "")))
    if not title:
        return None

    if source.via_google_news:
        title = _strip_publisher_suffix(title, entry)

    return NewsItem(
        id="",
        outlet=source.outlet,
        section=source.section,
        title=title,
        summary="" if source.via_google_news else _entry_summary(entry, title),
        link=str(entry.get("link", "")),
        published_at=_entry_datetime(entry),
        content="" if source.via_google_news else _entry_content(entry),
    )


def _entry_summary(entry: Any, title: str) -> str:
    summary = clean_text(str(entry.get("summary", "")))
    return "" if summary == title else summary


def _entry_content(entry: Any) -> str:
    blocks = entry.get("content") or []
    return clean_text(" ".join(str(block.get("value", "")) for block in blocks))


def _entry_datetime(entry: Any) -> datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        value = entry.get(key)
        if value:
            return datetime.fromtimestamp(calendar.timegm(value), UTC)
    return None


def _strip_publisher_suffix(title: str, entry: Any) -> str:
    source = entry.get("source") or {}
    publisher = clean_text(str(source.get("title", "")))
    if publisher and title.endswith(f" - {publisher}"):
        return title[: -len(f" - {publisher}")].strip()

    head, separator, tail = title.rpartition(" - ")
    if separator and len(tail.split()) <= PUBLISHER_SUFFIX_MAX_WORDS:
        return head.strip()
    return title


def _deduplicate(items: list[NewsItem]) -> list[NewsItem]:
    seen: set[tuple[str, str]] = set()
    unique: list[NewsItem] = []
    for item in items:
        key = (item.outlet, item.title.casefold())
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def _number_items(items: list[NewsItem]) -> list[NewsItem]:
    ordered = sorted(items, key=_sort_key)
    return [
        item.model_copy(update={"id": str(index)})
        for index, item in enumerate(ordered, start=1)
    ]


def _sort_key(item: NewsItem) -> datetime:
    return item.published_at or datetime.max.replace(tzinfo=UTC)


def format_for_selection(items: list[NewsItem], local_tz: ZoneInfo) -> str:
    return "\n".join(_selection_line(item, local_tz) for item in items)


def _selection_line(item: NewsItem, local_tz: ZoneInfo) -> str:
    when = (
        item.published_at.astimezone(local_tz).strftime("%d/%m %H:%M")
        if item.published_at
        else "sem horário"
    )
    line = f"[{item.id}] {item.outlet} · {item.section} · {when} · {item.title}"
    summary = item.summary[:SELECTION_SUMMARY_CHARS]
    return f"{line} — {summary}" if summary else line

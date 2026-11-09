import asyncio

import httpx
import pytest

from news_podcast.api.episode import articles
from news_podcast.api.episode.articles import (
    allows_full_text,
    build_briefs,
    is_video_page,
    other_headlines,
    pick_items,
)
from news_podcast.api.episode.schemas import NewsItem, SelectedStory, SourceText


def make_item(item_id: str, outlet: str, link: str) -> NewsItem:
    return NewsItem(
        id=item_id,
        outlet=outlet,
        section="Política",
        title=f"Manchete {item_id}",
        summary=f"Resumo {item_id}",
        link=link,
        published_at=None,
    )


SBT_LINK = "https://news.google.com/rss/articles/sbt"
SBT_VIDEO = "https://sbtnews.sbt.com.br/videos/XiOOB97yRhc"

ITEMS = {
    "1": make_item("1", "Folha", "https://www1.folha.uol.com.br/poder/a.shtml"),
    "2": make_item("2", "g1", "https://g1.globo.com/politica/b.ghtml"),
    "3": make_item("3", "g1", "https://g1.globo.com/politica/c.ghtml"),
    "4": make_item("4", "ICL Notícias", "https://news.google.com/rss/articles/x"),
    "5": make_item("5", "Poder360", "https://www.poder360.com.br/d/"),
    "6": make_item("6", "Estadão", "https://www.estadao.com.br/e/"),
    "7": make_item("7", "SBT News", SBT_LINK),
}


def test_full_text_only_for_open_sites() -> None:
    assert allows_full_text("https://g1.globo.com/politica/noticia.ghtml")
    assert allows_full_text("https://www.poder360.com.br/poder-gov/x/")
    assert not allows_full_text("https://www1.folha.uol.com.br/poder/x.shtml")
    assert not allows_full_text("https://www.estadao.com.br/politica/x/")
    assert not allows_full_text("https://noticias.uol.com.br/politica/x.htm")


def test_a_video_page_has_a_video_segment_in_its_path() -> None:
    assert is_video_page(SBT_VIDEO)
    assert is_video_page("https://www.bbc.com/portuguese/videos/c1abc")
    assert not is_video_page(
        "https://g1.globo.com/tecnologia/noticia/2026/11/09/video-game.ghtml"
    )
    assert not is_video_page(SBT_LINK)


def test_pick_items_reads_icl_first_then_open_sites_once_per_outlet() -> None:
    story = SelectedStory(title="x", item_ids=["1", "2", "3", "4", "5", "6"])

    picked = pick_items(story, ITEMS, {})

    assert [item.id for item in picked] == ["4", "2", "5"]


def test_a_video_page_is_not_picked_for_reading() -> None:
    story = SelectedStory(title="x", item_ids=["7", "2", "5", "1"])

    picked = pick_items(story, ITEMS, {SBT_LINK: SBT_VIDEO})

    assert [item.id for item in picked] == ["2", "5", "1"]


def test_a_video_page_leaves_its_slot_to_another_outlet(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    story = SelectedStory(title="x", item_ids=["7", "2", "5", "1"])

    async def resolve(links: list[str]) -> dict[str, str]:
        return {SBT_LINK: SBT_VIDEO} if SBT_LINK in links else {}

    async def read(_client: httpx.AsyncClient, item: NewsItem, url: str) -> SourceText:
        return SourceText(outlet=item.outlet, title=item.title, text=url)

    monkeypatch.setattr(articles, "resolve_google_news_links", resolve)
    monkeypatch.setattr(articles, "read_source", read)

    async def scenario() -> list[str]:
        async with httpx.AsyncClient() as client:
            [brief] = await build_briefs(client, [story], ITEMS)
            return [source.outlet for source in brief.sources]

    assert asyncio.run(scenario()) == ["g1", "Poder360", "Folha"]


def test_other_headlines_cover_the_outlets_not_read() -> None:
    story = SelectedStory(title="x", item_ids=["1", "2", "3", "4", "5", "6"])

    headlines = other_headlines(story, pick_items(story, ITEMS, {}), ITEMS)

    assert [headline.outlet for headline in headlines] == ["Folha", "Estadão"]

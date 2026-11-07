from news_podcast.api.episode.articles import (
    allows_full_text,
    other_headlines,
    pick_items,
)
from news_podcast.api.episode.schemas import NewsItem, SelectedStory


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


ITEMS = {
    "1": make_item("1", "Folha", "https://www1.folha.uol.com.br/poder/a.shtml"),
    "2": make_item("2", "g1", "https://g1.globo.com/politica/b.ghtml"),
    "3": make_item("3", "g1", "https://g1.globo.com/politica/c.ghtml"),
    "4": make_item("4", "ICL Notícias", "https://news.google.com/rss/articles/x"),
    "5": make_item("5", "Poder360", "https://www.poder360.com.br/d/"),
    "6": make_item("6", "Estadão", "https://www.estadao.com.br/e/"),
}


def test_full_text_only_for_open_sites() -> None:
    assert allows_full_text("https://g1.globo.com/politica/noticia.ghtml")
    assert allows_full_text("https://www.poder360.com.br/poder-gov/x/")
    assert not allows_full_text("https://www1.folha.uol.com.br/poder/x.shtml")
    assert not allows_full_text("https://www.estadao.com.br/politica/x/")
    assert not allows_full_text("https://noticias.uol.com.br/politica/x.htm")


def test_pick_items_reads_icl_first_then_open_sites_once_per_outlet() -> None:
    story = SelectedStory(title="x", item_ids=["1", "2", "3", "4", "5", "6"])

    picked = pick_items(story, ITEMS)

    assert [item.id for item in picked] == ["4", "2", "5"]


def test_other_headlines_cover_the_outlets_not_read() -> None:
    story = SelectedStory(title="x", item_ids=["1", "2", "3", "4", "5", "6"])

    headlines = other_headlines(story, pick_items(story, ITEMS), ITEMS)

    assert [headline.outlet for headline in headlines] == ["Folha", "Estadão"]

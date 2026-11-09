from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from news_podcast.api.episode.config import OPML_PATH
from news_podcast.api.episode.feeds import (
    clean_text,
    format_for_selection,
    load_sources,
    outlet_name,
    parse_feed,
)
from news_podcast.api.episode.schemas import FeedSource

START = datetime(2026, 11, 5, 9, 0, tzinfo=UTC)
END = datetime(2026, 11, 6, 9, 0, tzinfo=UTC)

RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>g1</title>
<item><title>Camara aprova projeto</title><link>https://g1.globo.com/a</link>
<description>&lt;img src="x.jpg"/&gt;&lt;p&gt;Texto &amp;amp; resumo&lt;/p&gt;
</description>
<pubDate>Thu, 05 Nov 2026 18:00:00 -0300</pubDate></item>
<item><title>Noticia antiga</title><link>https://g1.globo.com/b</link>
<pubDate>Tue, 03 Nov 2026 10:00:00 -0300</pubDate></item>
<item><title>Sem data</title><link>https://g1.globo.com/c</link></item>
</channel></rss>"""

GOOGLE_NEWS_RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Google News</title>
<item><title>Juros sobem de novo - ICL Noticias</title>
<link>https://news.google.com/rss/articles/CBMiabc?oc=5</link>
<description>&lt;a href="x"&gt;Juros sobem de novo&lt;/a&gt;</description>
<pubDate>Thu, 05 Nov 2026 20:00:00 GMT</pubDate>
<source url="https://iclnoticias.com.br">ICL Noticias</source></item>
</channel></rss>"""


def make_source(via_google_news: bool = False) -> FeedSource:
    return FeedSource(
        outlet="g1",
        section="Política",
        url="https://example.com/feed",
        via_google_news=via_google_news,
    )


def test_load_sources_reads_every_feed_with_its_folder() -> None:
    sources = load_sources(OPML_PATH)

    assert len(sources) == 13
    assert {source.section for source in sources} == {
        "Economia",
        "Geral",
        "Mundo",
        "Política",
    }
    icl = next(source for source in sources if source.outlet == "ICL Notícias")
    assert icl.via_google_news


def test_the_sbt_search_leaves_its_video_pages_out() -> None:
    sources = load_sources(OPML_PATH)

    sbt = next(source for source in sources if source.outlet == "SBT News")
    assert "-site:sbtnews.sbt.com.br/videos" in sbt.url


def test_outlet_name_drops_section_and_google_news_suffix() -> None:
    assert outlet_name("Estadão · Economia") == "Estadão"
    assert outlet_name("ICL Notícias (via Google News)") == "ICL Notícias"
    assert outlet_name("Aos Fatos · Checagem (via Google News)") == "Aos Fatos"


def test_clean_text_removes_tags_and_entities() -> None:
    assert clean_text("<p>Texto &amp;amp; <b>resumo</b></p>") == "Texto &amp; resumo"


def test_parse_feed_keeps_only_items_inside_the_window() -> None:
    items = parse_feed(make_source(), RSS, START, END)

    titles = [item.title for item in items]
    assert titles == ["Camara aprova projeto", "Sem data"]
    assert items[0].summary == "Texto & resumo"
    assert items[1].published_at is None


def test_parse_feed_strips_publisher_from_google_news_titles() -> None:
    items = parse_feed(make_source(via_google_news=True), GOOGLE_NEWS_RSS, START, END)

    assert items[0].title == "Juros sobem de novo"
    assert items[0].summary == ""


def test_format_for_selection_shows_local_time() -> None:
    item = parse_feed(make_source(), RSS, START, END)[0].model_copy(update={"id": "7"})

    line = format_for_selection([item], ZoneInfo("America/Sao_Paulo"))

    assert line.startswith("[7] g1 · Política · 05/11 18:00 · Camara aprova projeto")

NEWS_WINDOW_HOURS = 24


# The Railway cron starts in the hour before the episode's hour, so the scheduled
# news window closes at :00 of the hour the run starts in.
NEWS_CUTOFF_HOURS_BEFORE_SEND = 1


MINUTES_PER_STORY = 1.5
SHORT_SCRIPT_RATIO = 0.85
FULL_TEXT_DOMAINS = (
    "g1.globo.com",
    "cnnbrasil.com.br",
    "poder360.com.br",
    "bbc.com",
    "iclnoticias.com.br",
    "sbtnews.sbt.com.br",
    "aosfatos.org",
)
PREFERRED_OUTLETS = ("ICL Notícias",)
MAX_SOURCES_PER_STORY = 3
MAX_OTHER_HEADLINES = 6
HEADLINE_SUMMARY_CHARS = 300
MAX_SOURCE_CHARS = 5000
SELECTION_SUMMARY_CHARS = 280
FEED_CONTENT_MIN_CHARS = 1200
UNDATED_ITEMS_PER_FEED = 15
HTTP_TIMEOUT_SECONDS = 25.0
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)

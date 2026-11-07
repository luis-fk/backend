from datetime import date, time
from pathlib import Path
from zoneinfo import ZoneInfo

from news_podcast.api.episode.schemas import Host, ModelPrice, VoiceOption

APP_DIR = Path(__file__).resolve().parents[2]
OPML_PATH = APP_DIR / "feeds.opml"
OUTPUT_DIR = APP_DIR.parent / "news_podcast_output"
LOCAL_TZ = ZoneInfo("America/Sao_Paulo")

NEWS_WINDOW_HOURS = 24
# The workflow starts at :10 of the hour before the send time, so the scheduled
# news window closes at :00 of that hour.
NEWS_CUTOFF_HOURS_BEFORE_SEND = 1
MAX_WAIT_SECONDS = 3 * 60 * 60

DEFAULT_SEND_AT = time(7, 0)
DEFAULT_MIN_MINUTES = 12
DEFAULT_MAX_MINUTES = 18
DEFAULT_SPEECH_SPEED = 1.0
SHORTEST_EPISODE_MINUTES = 5
# Each voice request covers about 4 minutes of speech and the free tier allows 10
# requests a day, so 30 minutes (about 8 requests) leaves room for a retry.
MAX_SPEECH_MINUTES = 30
SPEECH_SPEED_LIMITS = (0.5, 2.0)
NATURAL_WORDS_PER_MINUTE = 170
MINUTES_PER_STORY = 1.5
SHORT_SCRIPT_RATIO = 0.85

HOSTS = (
    Host(
        name="Bia",
        speaker_id="Bia",
        gemini_voice="Kore",
        microsoft_voice="pt-BR-FranciscaNeural",
    ),
    Host(
        name="Léo",
        speaker_id="Leo",
        gemini_voice="Charon",
        microsoft_voice="pt-BR-AntonioNeural",
    ),
)
ALTERNATIVE_HOSTS = (
    HOSTS[0]._replace(gemini_voice="Aoede"),
    HOSTS[1]._replace(gemini_voice="Puck"),
)
SAMPLE_DIALOGUE = (
    "Bom dia! Este é um teste rápido pra você comparar as vozes do seu resumo de "
    "notícias.",
    "A ideia é ouvir o mesmo trecho com cada opção. Repara na entonação, nas pausas "
    "e no ritmo da conversa.",
    "E em como cada voz lê números e nomes, tipo uma inflação de 4,5% em doze meses, "
    "o dólar a R$ 5,50 ou nomes como Haddad, Alcolumbre e Zelensky.",
    "No fim, vale a que for mais agradável de ouvir todo dia, por uns dez minutos.",
    "Escolheu? É só configurar no GitHub. Até amanhã!",
)

TEXT_MODEL = "gemini-3.8-flash"
TEXT_FALLBACK_MODEL = "gemini-3.6-flash"
THINKING_LEVEL = "medium"

DEFAULT_VOICE: VoiceOption = "gemini-flash-lite"
TTS_MODELS: dict[VoiceOption, str] = {
    "gemini-flash": "gemini-3.8-flash-tts",
    "gemini-flash-lite": "gemini-3.8-flash-lite-tts",
}
TTS_STYLE = (
    "Warm, conversational news podcast host speaking Brazilian Portuguese "
    "with a neutral Brazilian accent; clear diction; brisk, fast pace."
)
HEADLINE_TTS_STYLE = (
    "Brazilian TV news anchor reading the opening headlines: firm, emphatic and "
    "impactful delivery that stresses the key words, with a brief pause at the end; "
    "neutral Brazilian accent; clear diction."
)
TTS_CHUNK_WORDS = 650
GEMINI_GAP_SECONDS = 0.25
MICROSOFT_GAP_SECONDS = 0.35
MICROSOFT_RATE = "+6%"
AUDIO_TOKENS_PER_SECOND = 25
VOICE_RETRY_MINUTES = (10, 20)

PRICE_CHANGE_DAY = date(2027, 1, 1)
PRICES: dict[str, tuple[ModelPrice, ModelPrice]] = {
    "gemini-3.8-flash": (ModelPrice(0.75, 3.75), ModelPrice(1.50, 7.50)),
    "gemini-3.6-flash": (ModelPrice(0.75, 3.75), ModelPrice(1.50, 7.50)),
    "gemini-3.8-flash-tts": (ModelPrice(0.50, 9.00), ModelPrice(1.00, 18.00)),
    "gemini-3.8-flash-lite-tts": (ModelPrice(0.50, 6.00), ModelPrice(1.00, 12.00)),
}
MODEL_LABELS: dict[str, str] = {
    "gemini-3.8-flash": "Gemini 3.8 Flash",
    "gemini-3.6-flash": "Gemini 3.6 Flash",
    "gemini-3.8-flash-tts": "Gemini 3.8 Flash TTS",
    "gemini-3.8-flash-lite-tts": "Gemini 3.8 Flash-Lite TTS",
}
BRL_PER_USD = 5.50

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

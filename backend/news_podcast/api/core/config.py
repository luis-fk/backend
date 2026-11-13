from pathlib import Path
from zoneinfo import ZoneInfo

from news_podcast.api.core.schemas import Host

APP_DIR = Path(__file__).resolve().parents[2]
OUTPUT_DIR = APP_DIR.parent / "news_podcast_output"
LOCAL_TZ = ZoneInfo("America/Sao_Paulo")
SHORTEST_EPISODE_MINUTES = 5


# Each voice request covers about 4 minutes of speech and the free tier allows 10
# requests a day, so 30 minutes (about 8 requests) leaves room for a retry.
MAX_SPEECH_MINUTES = 30
SPEECH_SPEED_LIMITS = (0.5, 2.0)
NATURAL_WORDS_PER_MINUTE = 170
HOSTS = (
    Host(name="Bia", speaker_id="Bia", gemini_voice="Kore"),
    Host(name="Léo", speaker_id="Leo", gemini_voice="Charon"),
)
THINKING_LEVEL = "medium"
TTS_CHUNK_WORDS = 650
AUDIO_TOKENS_PER_SECOND = 25
VOICE_RETRY_MINUTES = (10, 20)
TEXT_RETRY_MINUTES = (10, 20)


# Railway doesn't start a scheduled run while the previous one is still running, so a
# stuck run would block the next days. Two hours fit a run that waits for the text and
# the voice retries.
MAX_RUN_MINUTES = 120
BRL_PER_USD = 5.50

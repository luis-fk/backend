from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from news_podcast.api.core.config import NATURAL_WORDS_PER_MINUTE
from news_podcast.api.episode.config import MINUTES_PER_STORY
from news_podcast.api.episode.schemas import EpisodeOptions

PODCAST_NAMES = {
    0: "Resumo da meia-noite",
    1: "Resumo da 1",
    12: "Resumo do meio-dia",
}


def target_minutes(options: EpisodeOptions) -> float:
    return (options.min_minutes + options.max_minutes) / 2


def words_per_minute(options: EpisodeOptions) -> int:
    return round(NATURAL_WORDS_PER_MINUTE * options.speech_speed)


def word_range(options: EpisodeOptions) -> tuple[int, int]:
    pace = words_per_minute(options)
    return options.min_minutes * pace, options.max_minutes * pace


def story_range(options: EpisodeOptions) -> tuple[int, int]:
    return (
        round(options.min_minutes / MINUTES_PER_STORY),
        round(options.max_minutes / MINUTES_PER_STORY),
    )


def podcast_name(send_at: time) -> str:
    return PODCAST_NAMES.get(send_at.hour, f"Resumo das {send_at.hour}")


def greeting(send_at: time) -> str:
    if 5 <= send_at.hour < 12:
        return "bom dia"
    if 12 <= send_at.hour < 18:
        return "boa tarde"
    return "boa noite"


def spoken_time(send_at: time) -> str:
    if send_at.minute:
        return f"{send_at.hour}h{send_at.minute:02d}"
    return f"{send_at.hour}h"


def next_send(now: datetime, local_tz: ZoneInfo) -> datetime:
    """The hour the episode is named after: the next full hour, in local time. A run
    that starts at 6h40 makes the 7h episode, so the Railway cron alone sets it."""
    local_now = now.astimezone(local_tz)
    return local_now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)


def news_window(
    now: datetime,
    scheduled_for: datetime | None,
    hours: int,
    hours_before_send: int,
) -> tuple[datetime, datetime]:
    if scheduled_for is None:
        return now - timedelta(hours=hours), now

    top_of_send_hour = scheduled_for.replace(minute=0, second=0, microsecond=0)
    end = top_of_send_hour - timedelta(hours=hours_before_send)
    return end - timedelta(hours=hours), end

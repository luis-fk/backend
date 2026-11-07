import re
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from news_podcast.api.episode import config
from news_podcast.api.episode.schemas import EpisodeOptions

MINUTES_PATTERN = re.compile(r"([0-9]+)\s*[-–]\s*([0-9]+)")
SEND_AT_PATTERN = re.compile(r"([01]?[0-9]|2[0-3]):([0-5][0-9])")
SPEED_PATTERN = re.compile(r"([0-9]+(?:[.,][0-9]+)?)x?", re.IGNORECASE)
PODCAST_NAMES = {
    0: "Resumo da meia-noite",
    1: "Resumo da 1",
    12: "Resumo do meio-dia",
}


class InvalidOptionError(Exception):
    pass


def parse_episode_options(
    minutes: str | None, send_at: str | None, speech_speed: str | None
) -> EpisodeOptions:
    min_minutes, max_minutes = parse_minutes(minutes)
    speed = parse_speech_speed(speech_speed)
    speech_minutes = max_minutes * speed
    if speech_minutes > config.MAX_SPEECH_MINUTES:
        raise InvalidOptionError(
            f"{max_minutes} minutos em {speed:g}x são {speech_minutes:g} minutos de "
            f"fala, e o limite é {config.MAX_SPEECH_MINUTES}. Diminua o máximo de "
            "NEWS_PODCAST_MINUTES ou a NEWS_PODCAST_SPEECH_SPEED"
        )
    return EpisodeOptions(min_minutes, max_minutes, parse_send_at(send_at), speed)


def parse_minutes(raw: str | None) -> tuple[int, int]:
    value = (raw or "").strip()
    if not value:
        return config.DEFAULT_MIN_MINUTES, config.DEFAULT_MAX_MINUTES

    match = MINUTES_PATTERN.fullmatch(value)
    if not match:
        raise InvalidOptionError(
            "NEWS_PODCAST_MINUTES precisa ter o mínimo e o máximo, como 12-18 "
            f"(veio {value!r})"
        )
    shortest, longest = int(match.group(1)), int(match.group(2))
    if shortest > longest:
        raise InvalidOptionError(
            f"NEWS_PODCAST_MINUTES tem o mínimo maior que o máximo (veio {value!r})"
        )
    if shortest < config.SHORTEST_EPISODE_MINUTES:
        raise InvalidOptionError(
            "NEWS_PODCAST_MINUTES precisa começar em pelo menos "
            f"{config.SHORTEST_EPISODE_MINUTES} minutos (veio {value!r})"
        )
    return shortest, longest


def parse_send_at(raw: str | None) -> time:
    value = (raw or "").strip()
    if not value:
        return config.DEFAULT_SEND_AT

    match = SEND_AT_PATTERN.fullmatch(value)
    if not match:
        raise InvalidOptionError(
            "NEWS_PODCAST_SEND_AT precisa ser um horário no formato HH:MM, como 07:00 "
            f"ou 21:30 (veio {value!r})"
        )
    return time(int(match.group(1)), int(match.group(2)))


def parse_speech_speed(raw: str | None) -> float:
    value = (raw or "").strip()
    if not value:
        return config.DEFAULT_SPEECH_SPEED

    match = SPEED_PATTERN.fullmatch(value)
    speed = float(match.group(1).replace(",", ".")) if match else None
    slowest, fastest = config.SPEECH_SPEED_LIMITS
    if speed is None or not slowest <= speed <= fastest:
        raise InvalidOptionError(
            f"NEWS_PODCAST_SPEECH_SPEED precisa ser um número de {slowest:g} a "
            f"{fastest:g}, como 1.25 (veio {value!r})"
        )
    return speed


def target_minutes(options: EpisodeOptions) -> float:
    return (options.min_minutes + options.max_minutes) / 2


def words_per_minute(options: EpisodeOptions) -> int:
    return round(config.NATURAL_WORDS_PER_MINUTE * options.speech_speed)


def word_range(options: EpisodeOptions) -> tuple[int, int]:
    pace = words_per_minute(options)
    return options.min_minutes * pace, options.max_minutes * pace


def story_range(options: EpisodeOptions) -> tuple[int, int]:
    return (
        round(options.min_minutes / config.MINUTES_PER_STORY),
        round(options.max_minutes / config.MINUTES_PER_STORY),
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


def nearest_send(now: datetime, send_at: time, local_tz: ZoneInfo) -> datetime:
    local_now = now.astimezone(local_tz)
    same_day = datetime.combine(local_now.date(), send_at, tzinfo=local_tz)
    candidates = (
        same_day - timedelta(days=1),
        same_day,
        same_day + timedelta(days=1),
    )
    return min(candidates, key=lambda moment: abs(moment - local_now))

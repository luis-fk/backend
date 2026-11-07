from datetime import datetime, time
from zoneinfo import ZoneInfo

import pytest

from news_podcast.api.episode.options import (
    InvalidOptionError,
    greeting,
    nearest_send,
    parse_episode_options,
    podcast_name,
    spoken_time,
    story_range,
    word_range,
)
from news_podcast.api.episode.schemas import EpisodeOptions

SAO_PAULO = ZoneInfo("America/Sao_Paulo")
DEFAULTS = EpisodeOptions(12, 18, time(7, 0), 1.0)


def test_missing_or_empty_variables_keep_the_defaults() -> None:
    assert parse_episode_options(None, None, None) == DEFAULTS
    assert parse_episode_options("", " ", "") == DEFAULTS


def test_variables_accept_the_formats_shown_in_the_readme() -> None:
    assert parse_episode_options("10-15", "21:00", "1.25") == EpisodeOptions(
        10, 15, time(21, 0), 1.25
    )
    assert parse_episode_options(" 8 – 12 ", "7:30", "1,5x") == EpisodeOptions(
        8, 12, time(7, 30), 1.5
    )


@pytest.mark.parametrize(
    ("minutes", "send_at", "speed", "message"),
    [
        ("15", None, None, "como 12-18"),
        ("18-12", None, None, "mínimo maior que o máximo"),
        ("3-6", None, None, "pelo menos 5 minutos"),
        (None, "21h", None, "formato HH:MM"),
        (None, "24:00", None, "formato HH:MM"),
        (None, None, "rápido", "de 0.5 a 2"),
        (None, None, "3", "de 0.5 a 2"),
        (None, None, "2", "36 minutos de fala"),
    ],
)
def test_invalid_values_say_what_is_wrong(
    minutes: str | None, send_at: str | None, speed: str | None, message: str
) -> None:
    with pytest.raises(InvalidOptionError, match=message):
        parse_episode_options(minutes, send_at, speed)


def test_story_count_follows_the_length() -> None:
    assert story_range(DEFAULTS) == (8, 12)
    assert story_range(DEFAULTS._replace(min_minutes=6, max_minutes=9)) == (4, 6)


def test_faster_speech_needs_a_longer_script_for_the_same_length() -> None:
    assert word_range(DEFAULTS) == (2040, 3060)
    assert word_range(DEFAULTS._replace(speech_speed=1.5)) == (3060, 4590)


@pytest.mark.parametrize(
    ("send_at", "name", "hello", "spoken"),
    [
        (time(7, 0), "Resumo das 7", "bom dia", "7h"),
        (time(12, 0), "Resumo do meio-dia", "boa tarde", "12h"),
        (time(21, 30), "Resumo das 21", "boa noite", "21h30"),
        (time(0, 15), "Resumo da meia-noite", "boa noite", "0h15"),
        (time(1, 0), "Resumo da 1", "boa noite", "1h"),
    ],
)
def test_name_and_greeting_follow_the_send_time(
    send_at: time, name: str, hello: str, spoken: str
) -> None:
    assert podcast_name(send_at) == name
    assert greeting(send_at) == hello
    assert spoken_time(send_at) == spoken


def test_scheduled_run_belongs_to_the_send_time_later_that_day() -> None:
    now = datetime(2026, 11, 7, 6, 10, tzinfo=SAO_PAULO)

    assert nearest_send(now, time(7, 0), SAO_PAULO) == datetime(
        2026, 11, 7, 7, 0, tzinfo=SAO_PAULO
    )


def test_late_run_belongs_to_the_send_time_that_just_passed() -> None:
    now = datetime(2026, 11, 7, 7, 5, tzinfo=SAO_PAULO)

    assert nearest_send(now, time(7, 0), SAO_PAULO) == datetime(
        2026, 11, 7, 7, 0, tzinfo=SAO_PAULO
    )


def test_run_before_midnight_belongs_to_the_next_day() -> None:
    now = datetime(2026, 11, 7, 23, 10, tzinfo=SAO_PAULO)

    assert nearest_send(now, time(0, 30), SAO_PAULO) == datetime(
        2026, 11, 8, 0, 30, tzinfo=SAO_PAULO
    )

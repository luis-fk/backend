from datetime import datetime, time
from zoneinfo import ZoneInfo

import pytest

from news_podcast.api.episode.options import (
    greeting,
    next_send,
    podcast_name,
    spoken_time,
    story_range,
    word_range,
)
from news_podcast.api.episode.schemas import EpisodeOptions

SAO_PAULO = ZoneInfo("America/Sao_Paulo")
DEFAULTS = EpisodeOptions(12, 18, 1.0)


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


def test_a_run_sends_at_the_next_full_hour() -> None:
    now = datetime(2026, 11, 7, 6, 10, tzinfo=SAO_PAULO)

    assert next_send(now, SAO_PAULO) == datetime(2026, 11, 7, 7, 0, tzinfo=SAO_PAULO)


def test_a_run_on_the_hour_sends_an_hour_later() -> None:
    now = datetime(2026, 11, 7, 9, 0, tzinfo=SAO_PAULO)

    assert next_send(now, SAO_PAULO) == datetime(2026, 11, 7, 10, 0, tzinfo=SAO_PAULO)


def test_the_send_time_is_local_and_can_fall_on_the_next_day() -> None:
    # 23h10 in São Paulo is 02h10 UTC.
    now = datetime(2026, 11, 8, 2, 10, tzinfo=ZoneInfo("UTC"))

    assert next_send(now, SAO_PAULO) == datetime(2026, 11, 8, 0, 0, tzinfo=SAO_PAULO)

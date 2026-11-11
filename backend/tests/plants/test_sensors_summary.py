from datetime import UTC, datetime, timedelta

import pytest

from plants.api.sensors.summary import plant_summary, plants_overview
from plants.models import Esp32Data, Esp32Device
from tests.api_tokens import saved_device

DATABASES = pytest.mark.django_db(databases=["default", "plants_db"])
# 12:00 in São Paulo.
NOW = datetime(2026, 11, 11, 15, 0, tzinfo=UTC)


def add(
    device: Esp32Device,
    at: datetime,
    raw: int = 2048,
    temperature: int | None = 21,
    humidity: int | None = 60,
) -> None:
    row = Esp32Data.objects.create(
        analog_value=raw,
        digital_value=1,
        temperature=temperature,
        humidity=humidity,
        user=device.user,
        device=device,
    )
    Esp32Data.objects.filter(pk=row.pk).update(created_at=at)


@DATABASES
def test_the_overview_lists_each_plant_with_its_reading_times() -> None:
    device, _ = saved_device()
    for hours_ago in (3, 2, 1):
        add(device, NOW - timedelta(hours=hours_ago))

    assert plants_overview(device.user_id) == [
        {
            "plant": "Manjericão",
            "readings": 3,
            "first_reading": "2026-11-11 09:00",
            "last_reading": "2026-11-11 11:00",
            "usual_interval_minutes": 60,
        }
    ]


@DATABASES
def test_a_summary_gives_each_measure_s_last_min_max_average_and_change() -> None:
    device, _ = saved_device()
    for hours_ago, raw, temperature in [(3, 2048, 18), (2, 1024, 25), (1, 3071, 21)]:
        add(device, NOW - timedelta(hours=hours_ago), raw=raw, temperature=temperature)

    summary = plant_summary(device.user_id, "Manjericão", 24, now=NOW)

    assert (summary["plant"], summary["period_hours"], summary["readings"]) == (
        "Manjericão",
        24,
        3,
    )
    assert summary["measures"]["soil_percent"] == {
        "last": 25,
        "last_at": "2026-11-11 11:00",
        "min": 25,
        "min_at": "2026-11-11 11:00",
        "max": 75,
        "max_at": "2026-11-11 10:00",
        "average": 50.0,
        "change": -25,
    }
    assert summary["measures"]["temperature"]["average"] == 21.3
    assert summary["measures"]["temperature"]["change"] == 3
    assert [row["time"] for row in summary["series"]] == [
        "2026-11-11 09:00",
        "2026-11-11 10:00",
        "2026-11-11 11:00",
    ]


@DATABASES
def test_empty_weather_stays_out_of_the_statistics() -> None:
    device, _ = saved_device()
    add(device, NOW - timedelta(hours=3), temperature=None, humidity=None)
    add(device, NOW - timedelta(hours=2), temperature=20, humidity=50)
    add(device, NOW - timedelta(hours=1), temperature=None, humidity=None)

    summary = plant_summary(device.user_id, "Manjericão", 24, now=NOW)

    assert summary["without_weather"] == 2
    # The newest reading has no weather: the last temperature is an hour older.
    assert summary["measures"]["temperature"] == {
        "last": 20,
        "last_at": "2026-11-11 10:00",
        "min": 20,
        "min_at": "2026-11-11 10:00",
        "max": 20,
        "max_at": "2026-11-11 10:00",
        "average": 20.0,
        "change": None,
    }


@DATABASES
def test_long_periods_come_as_daily_averages_by_local_day() -> None:
    device, _ = saved_device()
    for hours_ago in range(1, 61):
        add(device, NOW - timedelta(hours=hours_ago))
    # 01:30 UTC on the 10th is 22:30 on the 9th in São Paulo.
    add(device, datetime(2026, 11, 10, 1, 30, tzinfo=UTC))

    summary = plant_summary(device.user_id, "Manjericão", 168, now=NOW)

    assert [(row["time"], row["readings"]) for row in summary["series"]] == [
        ("2026-11-09", 25),
        ("2026-11-10", 24),
        ("2026-11-11", 12),
    ]


@DATABASES
def test_an_unknown_plant_answers_with_the_person_s_plants() -> None:
    mine, _ = saved_device("Manjericão")
    theirs, _ = saved_device("Alecrim")
    namesake, _ = saved_device("Manjericão")
    add(mine, NOW - timedelta(hours=1))
    add(namesake, NOW - timedelta(hours=1))
    add(namesake, NOW - timedelta(hours=2))

    assert plant_summary(mine.user_id, "Alecrim", 24, now=NOW) == {
        "error": "No plant called Alecrim.",
        "plants": ["Manjericão"],
    }
    assert plant_summary(mine.user_id, "Manjericão", 24, now=NOW)["readings"] == 1


@DATABASES
def test_a_plant_is_found_ignoring_case() -> None:
    device, _ = saved_device()
    add(device, NOW - timedelta(hours=1))

    assert plant_summary(device.user_id, "manjericão", 24, now=NOW)["plant"] == (
        "Manjericão"
    )


@DATABASES
def test_a_single_reading_has_no_change() -> None:
    device, _ = saved_device()
    add(device, NOW - timedelta(hours=1))

    summary = plant_summary(device.user_id, "Manjericão", 24, now=NOW)

    assert summary["measures"]["soil_percent"]["change"] is None


@DATABASES
@pytest.mark.parametrize(("asked", "kept"), [(0, 1), (24, 24), (5000, 720)])
def test_the_period_is_kept_between_1_and_720_hours(asked: int, kept: int) -> None:
    device, _ = saved_device()

    assert (
        plant_summary(device.user_id, "Manjericão", asked, now=NOW)["period_hours"]
        == kept
    )

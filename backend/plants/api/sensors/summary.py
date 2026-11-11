"""What the plants chat's tools tell the model about the person's plants, with
times in São Paulo's zone, where the owner lives."""

from datetime import datetime, timedelta
from statistics import median
from typing import Any, Literal
from zoneinfo import ZoneInfo

from django.utils import timezone

from plants.api.sensors.service import Reading, readings_of
from plants.models import Esp32Device

LOCAL_TIME = ZoneInfo("America/Sao_Paulo")
MAX_HOURS = 720
# Up to this many readings come one by one; more come as averages.
MAX_READINGS = 48

Measure = Literal["soil_percent", "soil_raw", "air_humidity", "temperature"]
MEASURES: tuple[Measure, ...] = (
    "soil_percent",
    "soil_raw",
    "air_humidity",
    "temperature",
)


def local(time: datetime) -> str:
    return time.astimezone(LOCAL_TIME).strftime("%Y-%m-%d %H:%M")


def plants_overview(user_id: int) -> list[dict[str, Any]]:
    """The person's active plants, each with its number of readings, the first and
    last reading times, and the usual interval between readings."""
    overview = []
    devices = Esp32Device.objects.filter(user_id=user_id, active=True)
    for device in devices.order_by("nickname"):
        times = list(
            device.readings.order_by("created_at").values_list("created_at", flat=True)
        )
        gaps = [
            (later - earlier).total_seconds() / 60
            for earlier, later in zip(times, times[1:])
        ]
        overview.append(
            {
                "plant": device.nickname,
                "readings": len(times),
                "first_reading": local(times[0]) if times else None,
                "last_reading": local(times[-1]) if times else None,
                "usual_interval_minutes": round(median(gaps)) if gaps else None,
            }
        )
    return overview


def find_plant(user_id: int, plant: str) -> Esp32Device | None:
    """The person's active plant by nickname: as typed first, then ignoring case
    when only one matches, since nicknames are unique per person only as typed."""
    devices = Esp32Device.objects.filter(user_id=user_id, active=True)
    name = plant.strip()
    exact = devices.filter(nickname=name).first()
    if exact is not None:
        return exact
    loose = list(devices.filter(nickname__iexact=name)[:2])
    return loose[0] if len(loose) == 1 else None


def statistics_of(points: list[tuple[datetime, int]]) -> dict[str, Any] | None:
    """The last, lowest and highest values (with their times), the average and the
    change from the first to the last; None without values."""
    if not points:
        return None
    low = min(points, key=lambda point: point[1])
    high = max(points, key=lambda point: point[1])
    values = [value for _, value in points]
    return {
        "last": points[-1][1],
        # The weather can be missing from the newest readings, so the last value
        # says when it was measured.
        "last_at": local(points[-1][0]),
        "min": low[1],
        "min_at": local(low[0]),
        "max": high[1],
        "max_at": local(high[0]),
        "average": round(sum(values) / len(values), 1),
        "change": points[-1][1] - points[0][1] if len(points) > 1 else None,
    }


def average(rows: list[Reading], measure: Measure) -> float | None:
    values = [value for row in rows if (value := row[measure]) is not None]
    return round(sum(values) / len(values), 1) if values else None


def series_of(readings: list[Reading], hours: int) -> list[dict[str, Any]]:
    """The readings themselves when few; otherwise averages per local hour over a
    day, or per local day over longer periods."""
    if len(readings) <= MAX_READINGS:
        return [
            {"time": local(reading["time"]), **{m: reading[m] for m in MEASURES}}
            for reading in readings
        ]
    period = "%Y-%m-%d %H:00" if hours <= 24 else "%Y-%m-%d"
    groups: dict[str, list[Reading]] = {}
    for reading in readings:
        key = reading["time"].astimezone(LOCAL_TIME).strftime(period)
        groups.setdefault(key, []).append(reading)
    return [
        {"time": key, "readings": len(rows), **{m: average(rows, m) for m in MEASURES}}
        for key, rows in groups.items()
    ]


def plant_summary(
    user_id: int, plant: str, hours: int, now: datetime | None = None
) -> dict[str, Any]:
    """One of the person's plants over the last hours (1 to 720): each measure's
    statistics, leaving out empty values, and the readings or their averages."""
    device = find_plant(user_id, plant)
    if device is None:
        nicknames = Esp32Device.objects.filter(user_id=user_id, active=True)
        return {
            "error": f"No plant called {plant}.",
            "plants": list(
                nicknames.order_by("nickname").values_list("nickname", flat=True)
            ),
        }

    hours = max(1, min(MAX_HOURS, hours))
    readings = readings_of(device, (now or timezone.now()) - timedelta(hours=hours))
    measures = {}
    for measure in MEASURES:
        points = [
            (reading["time"], value)
            for reading in readings
            if (value := reading[measure]) is not None
        ]
        measures[measure] = statistics_of(points)
    return {
        "plant": device.nickname,
        "period_hours": hours,
        "readings": len(readings),
        "without_weather": sum(
            1
            for reading in readings
            if reading["temperature"] is None or reading["air_humidity"] is None
        ),
        "measures": measures,
        "series": series_of(readings, hours),
    }

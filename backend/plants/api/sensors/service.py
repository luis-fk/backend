from datetime import datetime
from typing import TypedDict

from django.db.models import Max

from plants.models import Esp32Data, Esp32Device

# The tab's periods: a day, a week and 30 days.
ALLOWED_HOURS = (24, 168, 720)


class DeviceInfo(TypedDict):
    id: int
    nickname: str
    last_reading_at: datetime | None


class Reading(TypedDict):
    time: datetime
    soil_percent: int | None
    soil_raw: int
    air_humidity: int | None
    temperature: int | None


def devices_of(user_id: int) -> list[DeviceInfo]:
    """The person's active devices by nickname, with each one's newest reading
    time."""
    rows = (
        Esp32Device.objects.filter(user_id=user_id, active=True)
        .annotate(last_reading_at=Max("readings__created_at"))
        .order_by("nickname")
        .values("id", "nickname", "last_reading_at")
    )
    return [
        DeviceInfo(
            id=row["id"],
            nickname=row["nickname"],
            last_reading_at=row["last_reading_at"],
        )
        for row in rows
    ]


def device_of(user_id: int, device_id: int) -> Esp32Device | None:
    """The person's active device with this id."""
    return Esp32Device.objects.filter(
        pk=device_id, user_id=user_id, active=True
    ).first()


def readings_of(device: Esp32Device, since: datetime) -> list[Reading]:
    """The device's readings from since on, oldest first, with the soil as a
    percentage of its calibration and the weather that came with each one."""
    rows = Esp32Data.objects.filter(device=device, created_at__gte=since).order_by(
        "created_at", "id"
    )
    return [
        Reading(
            time=row.created_at,
            soil_percent=device.soil_percent(row.analog_value),
            soil_raw=row.analog_value,
            air_humidity=row.humidity,
            temperature=row.temperature,
        )
        for row in rows
    ]

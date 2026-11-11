import math
import random
from datetime import datetime, timedelta
from typing import Any, NamedTuple
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import router, transaction
from django.utils import timezone

from plants.models import Esp32Data, Esp32Device, Users

DEMO_USERNAME = "demo"
# A known password is fine, since the seed only runs on local databases: demo is
# also the admin's login there.
DEMO_PASSWORD = "demo"
SAO_PAULO = {"latitude": "-23.55", "longitude": "-46.63"}
SAO_PAULO_TIME = ZoneInfo("America/Sao_Paulo")
COOLEST_HOUR = 6
WARMEST_HOUR = 15
READING_INTERVAL = timedelta(hours=2)
READINGS = int(timedelta(days=30) / READING_INTERVAL)
JUST_WATERED = (1250, 1450)
NEEDS_WATER = (2900, 3200)
DIGITAL_DRY_ABOVE = 2600
# Fixed, so every run and every test draws the same numbers.
RANDOM_SEED = 42
# An empty host, or a path, is PostgreSQL's socket on this machine.
LOCAL_HOSTS = {"", "localhost", "127.0.0.1", "::1"}


class Plant(NamedTuple):
    """A sample plant. drying is how much its raw soil reading rises in 2 hours at
    the coolest hour; it doubles at the warmest."""

    nickname: str
    drying: float


PLANTS = (
    Plant("Manjericão", drying=38),  # watered every 2 to 3 days
    Plant("Samambaia", drying=21),  # every 4 to 5 days
)


class Weather(NamedTuple):
    temperature: int
    humidity: int


class Command(BaseCommand):
    help = "Gives demo two plants with 30 days of readings, on local databases only."

    def handle(self, *args: Any, **options: Any) -> None:
        remote = remote_databases()
        if remote:
            raise CommandError(
                f"Not local: {', '.join(remote)}. The seed only writes to the local "
                "databases; check backend/.env."
            )
        auth_user_id = demo_auth_user_id()
        with transaction.atomic(using=router.db_for_write(Esp32Device)):
            owner = demo_plants_row(auth_user_id)
            delete_sample_plants(owner)
            devices = sample_devices(owner)
        self.stdout.write(
            f"plants: log in as {DEMO_USERNAME}, with the password {DEMO_PASSWORD} "
            "in the admin"
        )
        self.stdout.write(
            f"plants: {READINGS} readings per plant, one every 2 hours for 30 days, "
            "in São Paulo"
        )
        for device, key in devices:
            self.stdout.write(
                f"plants: {device.nickname}, device {device.pk}, key {key}"
            )


def remote_databases() -> list[str]:
    """Each database outside this machine, as "alias (host)"."""
    remote: list[str] = []
    for alias, config in settings.DATABASES.items():
        host = config.get("HOST") or ""
        if "sqlite" in config["ENGINE"] or host in LOCAL_HOSTS or host.startswith("/"):
            continue
        remote.append(f"{alias} ({host})")
    return remote


def demo_auth_user_id() -> int:
    """demo's id in auth, let in again if it was blocked. The site takes the name,
    and the admin the password, which every run sets again."""
    demo, _ = get_user_model()._default_manager.get_or_create(username=DEMO_USERNAME)
    demo.set_password(DEMO_PASSWORD)
    demo.is_active = True
    demo.is_staff = True
    demo.is_superuser = True
    demo.save()
    return demo.pk


def demo_plants_row(auth_user_id: int) -> Users:
    row, _ = Users.objects.update_or_create(
        auth_user_id=auth_user_id, defaults={"active": True, **SAO_PAULO}
    )
    return row


def delete_sample_plants(owner: Users) -> None:
    """Deletes the sample plants an earlier run made, with their readings; the
    person's other devices stay."""
    owner.devices.filter(nickname__in=[plant.nickname for plant in PLANTS]).delete()


def sample_devices(owner: Users) -> list[tuple[Esp32Device, str]]:
    """The sample plants with their readings, each with its device's new key. Both
    read the same weather, since they live in the same place."""
    rng = random.Random(RANDOM_SEED)
    times = reading_times()
    weather = [weather_at(time, rng) for time in times]
    devices = []
    for plant in PLANTS:
        device, key = new_device(owner, plant.nickname)
        save_readings(device, times, weather, soil_readings(plant, times, rng))
        devices.append((device, key))
    return devices


def reading_times() -> list[datetime]:
    """Oldest first, ending at the current hour."""
    newest = timezone.now().replace(minute=0, second=0, microsecond=0)
    return [newest - READING_INTERVAL * k for k in reversed(range(READINGS))]


def warmth(time: datetime) -> float:
    """How warm the hour is in São Paulo: 0 at the coolest hour, 1 at the warmest,
    rising and falling smoothly in between."""
    hours = (time.astimezone(SAO_PAULO_TIME).hour - COOLEST_HOUR) % 24
    warming = WARMEST_HOUR - COOLEST_HOUR
    progress = hours / warming if hours <= warming else (24 - hours) / (24 - warming)
    return (1 - math.cos(math.pi * progress)) / 2


def weather_at(time: datetime, rng: random.Random) -> Weather:
    """About 17 °C and 90% humidity at the coolest hour, 28 °C and 45% at the
    warmest."""
    warm = warmth(time)
    return Weather(
        temperature=round(17 + 11 * warm + rng.uniform(-1, 1)),
        humidity=round(90 - 45 * warm + rng.uniform(-3, 3)),
    )


def soil_readings(plant: Plant, times: list[datetime], rng: random.Random) -> list[int]:
    """The raw soil reading at each time, higher when drier: it rises as the pot
    dries, faster in the warm hours, until the plant needs water and is watered."""
    raw = rng.uniform(JUST_WATERED[0], NEEDS_WATER[0])
    water_at = rng.uniform(*NEEDS_WATER)
    readings: list[int] = []
    for time in times:
        readings.append(round(raw))
        if raw >= water_at:
            raw = rng.uniform(*JUST_WATERED)
            water_at = rng.uniform(*NEEDS_WATER)
        else:
            raw += plant.drying * (1 + warmth(time)) * rng.uniform(0.8, 1.2)
    return readings


def new_device(owner: Users, nickname: str) -> tuple[Esp32Device, str]:
    device = Esp32Device(user=owner, nickname=nickname)
    key = device.generate_key()
    device.save()
    return device, key


def save_readings(
    device: Esp32Device, times: list[datetime], weather: list[Weather], soil: list[int]
) -> None:
    rows = Esp32Data.objects.bulk_create(
        Esp32Data(
            analog_value=raw,
            digital_value=int(raw > DIGITAL_DRY_ABOVE),
            temperature=reading.temperature,
            humidity=reading.humidity,
            user=device.user,
            device=device,
        )
        for raw, reading in zip(soil, weather, strict=True)
    )
    # created_at is set on insert (auto_now_add), so the times go in afterwards.
    for row, time in zip(rows, times, strict=True):
        row.created_at = time
    Esp32Data.objects.bulk_update(rows, ["created_at"])

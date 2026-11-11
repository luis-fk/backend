import re
from datetime import datetime, timedelta
from io import StringIO
from zoneinfo import ZoneInfo

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from plants.api.esp32.devices import device_for_key
from plants.api.sensors.service import readings_of
from plants.models import Esp32Data, Esp32Device, Users
from tests.api_tokens import saved_device

DATABASES = pytest.mark.django_db(databases=["default", "plants_db"])
NICKNAMES = ["Manjericão", "Samambaia"]
PRINTED_DEVICE = re.compile(
    r"^plants: (?P<nickname>.+), device (?P<id>\d+), "
    r"key (?P<key>dk_[A-Za-z0-9_-]{43})$",
    re.MULTILINE,
)
SAO_PAULO_TIME = ZoneInfo("America/Sao_Paulo")
AFTERNOON = range(13, 18)
DAWN = range(4, 9)
REMOTE = {
    "ENGINE": "django.db.backends.postgresql",
    "HOST": "x.proxy.rlwy.net",
    "PASSWORD": "secret-password",
}


def seed() -> str:
    out = StringIO()
    call_command("seed_plants", stdout=out)
    return out.getvalue()


def demo_row() -> Users:
    demo = get_user_model().objects.get(username="demo")
    return Users.objects.get(auth_user_id=demo.pk)


def demo_devices() -> list[Esp32Device]:
    return list(Esp32Device.objects.filter(user=demo_row()).order_by("nickname"))


def raw_steps(device: Esp32Device) -> list[int]:
    """How much the raw soil reading changes from each reading to the next."""
    raw = list(
        device.readings.order_by("created_at").values_list("analog_value", flat=True)
    )
    return [after - before for before, after in zip(raw, raw[1:])]


def waterings(device: Esp32Device) -> int:
    return len([step for step in raw_steps(device) if step < -1000])


def weather(device: Esp32Device) -> dict[datetime, tuple[int, int]]:
    """The temperature and humidity at each reading time, from the readings that
    have them."""
    rows = device.readings.values_list("created_at", "temperature", "humidity")
    return {
        time: (temperature, humidity)
        for time, temperature, humidity in rows
        if temperature is not None and humidity is not None
    }


def weather_at_hours(device: Esp32Device, hours: range) -> tuple[list[int], list[int]]:
    """The temperatures and the humidities read at these hours of São Paulo."""
    readings = [
        values
        for time, values in weather(device).items()
        if time.astimezone(SAO_PAULO_TIME).hour in hours
    ]
    return [temperature for temperature, _ in readings], [
        humidity for _, humidity in readings
    ]


@DATABASES
def test_demo_can_use_plants_from_sao_paulo_and_the_admin() -> None:
    seed()

    demo = get_user_model().objects.get(username="demo")
    row = Users.objects.get(auth_user_id=demo.pk)
    assert demo.is_active
    assert demo.is_staff and demo.is_superuser
    assert demo.check_password("demo")
    assert row.active
    assert (row.latitude, row.longitude) == ("-23.55", "-46.63")


@DATABASES
def test_the_output_says_how_to_log_in() -> None:
    assert "plants: log in as demo, with the password demo in the admin" in seed()


@DATABASES
def test_a_blocked_demo_can_use_plants_again() -> None:
    demo = get_user_model().objects.create_user(username="demo", is_active=False)
    Users.objects.create(auth_user_id=demo.pk, active=False)

    seed()

    demo.refresh_from_db()
    row = Users.objects.get(auth_user_id=demo.pk)
    assert demo.is_active and demo.is_superuser
    assert demo.check_password("demo")
    assert row.active
    assert (row.latitude, row.longitude) == ("-23.55", "-46.63")


@DATABASES
def test_demo_has_two_plants_read_every_2_hours_for_30_days() -> None:
    seed()

    devices = demo_devices()
    assert [device.nickname for device in devices] == NICKNAMES
    for device in devices:
        times = list(
            device.readings.order_by("created_at").values_list("created_at", flat=True)
        )
        assert len(times) == 360
        gaps = {later - earlier for earlier, later in zip(times, times[1:])}
        assert gaps == {timedelta(hours=2)}
        assert timedelta(0) <= timezone.now() - times[-1] < timedelta(hours=1)
        assert times[-1] - times[0] == timedelta(hours=718)


@DATABASES
def test_both_plants_read_the_same_weather() -> None:
    seed()

    manjericao, samambaia = demo_devices()
    assert len(weather(manjericao)) == 360
    assert weather(manjericao) == weather(samambaia)


@DATABASES
def test_afternoons_are_warmer_and_drier_than_dawns_in_sao_paulo() -> None:
    seed()

    device = demo_devices()[0]
    afternoon_temperatures, afternoon_humidities = weather_at_hours(device, AFTERNOON)
    dawn_temperatures, dawn_humidities = weather_at_hours(device, DAWN)
    assert min(afternoon_temperatures) > max(dawn_temperatures)
    assert max(afternoon_humidities) < min(dawn_humidities)


@DATABASES
def test_each_plant_dries_until_it_is_watered() -> None:
    seed()

    manjericao, samambaia = demo_devices()
    for device in (manjericao, samambaia):
        rows = list(device.readings.values_list("analog_value", "digital_value"))
        assert all(0 <= raw <= 4095 for raw, _ in rows)
        assert all(digital == int(raw > 2600) for raw, digital in rows)
        assert all(step >= 0 or step < -1000 for step in raw_steps(device))
        assert waterings(device) >= 1
    assert waterings(manjericao) > waterings(samambaia)


@DATABASES
def test_each_printed_key_works_for_its_device() -> None:
    output = seed()

    printed = {line["nickname"]: line for line in PRINTED_DEVICE.finditer(output)}
    for device in demo_devices():
        assert int(printed[device.nickname]["id"]) == device.pk
        assert device_for_key(printed[device.nickname]["key"]) == device


@DATABASES
def test_running_it_again_replaces_only_its_own_data() -> None:
    someone, their_key = saved_device("Manjericão")
    Esp32Data.objects.create(
        analog_value=2000, digital_value=0, user=someone.user, device=someone
    )
    seed()
    cactus = Esp32Device(user=demo_row(), nickname="Cacto")
    cactus_key = cactus.generate_key()
    cactus.save()
    Esp32Data.objects.create(
        analog_value=2100, digital_value=0, user=demo_row(), device=cactus
    )
    Esp32Data.objects.create(
        analog_value=1800, digital_value=0, user=demo_row(), device=None
    )

    seed()

    samples = [device for device in demo_devices() if device.nickname in NICKNAMES]
    assert [device.nickname for device in samples] == NICKNAMES
    assert [device.readings.count() for device in samples] == [360, 360]
    assert device_for_key(cactus_key) == cactus
    assert list(cactus.readings.values_list("analog_value", flat=True)) == [2100]
    assert Esp32Data.objects.filter(user=demo_row(), device=None).count() == 1
    assert device_for_key(their_key) == someone
    assert list(someone.readings.values_list("analog_value", flat=True)) == [2000]


@DATABASES
def test_the_sensors_tab_shows_a_day_and_30_days_of_readings() -> None:
    seed()
    now = timezone.now()

    for device in demo_devices():
        day = readings_of(device, now - timedelta(hours=24))
        month = readings_of(device, now - timedelta(hours=720))
        assert len(day) in {12, 13}
        assert len(month) == 360
        assert all(reading["soil_percent"] is not None for reading in month)


@DATABASES
def test_it_refuses_databases_on_another_machine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        settings,
        "DATABASES",
        {
            **settings.DATABASES,
            "plants_db": REMOTE,
            "news_podcast_db": {**REMOTE, "HOST": "y.proxy.rlwy.net"},
        },
    )

    with pytest.raises(CommandError) as error:
        seed()

    assert "plants_db (x.proxy.rlwy.net)" in str(error.value)
    assert "news_podcast_db (y.proxy.rlwy.net)" in str(error.value)
    assert "secret-password" not in str(error.value)
    assert not get_user_model().objects.exists()
    assert not Users.objects.exists()

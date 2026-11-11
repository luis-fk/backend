from datetime import datetime, timedelta
from typing import Any

import pytest
from django.test import Client
from django.utils import timezone

from plants.models import Esp32Data, Esp32Device, Users
from tests.api_tokens import (
    api_key_for,
    bearer,
    saved_device,
    saved_person,
    user_token,
)

DATABASES = pytest.mark.django_db(databases=["default", "plants_db"])
DEVICES_URL = "/api/plants/devices/"


def readings_url(device_id: int, hours: str = "168") -> str:
    return f"/api/plants/devices/{device_id}/readings/?hours={hours}"


def get(client: Client, url: str, owner: Users | None) -> tuple[int, Any]:
    headers = bearer(user_token("plants", str(owner.pk))) if owner else {}
    response = client.get(url, headers=headers)
    return response.status_code, response.json()


def reading(
    device: Esp32Device,
    hours_ago: float,
    raw: int = 2048,
    temperature: int | None = 21,
    humidity: int | None = 68,
) -> Esp32Data:
    row = Esp32Data.objects.create(
        analog_value=raw,
        digital_value=1,
        temperature=temperature,
        humidity=humidity,
        user=device.user,
        device=device,
    )
    # created_at is set on save (auto_now_add), so the age comes after it.
    Esp32Data.objects.filter(pk=row.pk).update(
        created_at=timezone.now() - timedelta(hours=hours_ago)
    )
    row.refresh_from_db()
    return row


def another_device(owner: Users, nickname: str, active: bool = True) -> Esp32Device:
    device = Esp32Device(user=owner, nickname=nickname, active=active)
    device.generate_key()
    device.save()
    return device


@DATABASES
def test_the_person_lists_only_their_active_devices(client: Client) -> None:
    samambaia, _ = saved_device("Samambaia")
    owner = samambaia.user
    manjericao = another_device(owner, "Manjericão")
    another_device(owner, "Antiga", active=False)
    saved_device("Jiboia")
    newest = reading(manjericao, hours_ago=1)
    reading(manjericao, hours_ago=5)

    status, devices = get(client, DEVICES_URL, owner)

    assert status == 200
    assert [(d["id"], d["nickname"]) for d in devices] == [
        (manjericao.pk, "Manjericão"),
        (samambaia.pk, "Samambaia"),
    ]
    assert datetime.fromisoformat(devices[0]["last_reading_at"]) == newest.created_at
    assert devices[1]["last_reading_at"] is None


@DATABASES
def test_the_readings_come_in_time_order_within_the_period(client: Client) -> None:
    device, _ = saved_device()
    Esp32Device.objects.filter(pk=device.pk).update(dry_value=3000, wet_value=1000)
    newer = reading(device, hours_ago=2, raw=2000)
    older = reading(device, hours_ago=30, raw=2500)
    reading(device, hours_ago=200, raw=2900)

    status, body = get(client, readings_url(device.pk), device.user)

    assert status == 200
    rows = body["readings"]
    assert [(r["soil_raw"], r["soil_percent"]) for r in rows] == [
        (2500, 25),
        (2000, 50),
    ]
    assert [datetime.fromisoformat(r["time"]) for r in rows] == [
        older.created_at,
        newer.created_at,
    ]
    assert (rows[0]["air_humidity"], rows[0]["temperature"]) == (68, 21)


@DATABASES
def test_readings_without_the_weather_come_with_nulls(client: Client) -> None:
    device, _ = saved_device()
    reading(device, hours_ago=1, temperature=None, humidity=None)

    status, body = get(client, readings_url(device.pk, "24"), device.user)

    assert status == 200
    [row] = body["readings"]
    assert (row["air_humidity"], row["temperature"]) == (None, None)


@DATABASES
def test_another_person_s_device_or_an_unknown_one_gets_404(client: Client) -> None:
    mine, _ = saved_device("Manjericão")
    theirs, _ = saved_device("Manjericão")
    not_found = (404, {"error": "Device not found."})

    assert get(client, readings_url(theirs.pk), mine.user) == not_found
    assert get(client, readings_url(9999), mine.user) == not_found


@DATABASES
@pytest.mark.parametrize(
    "hours",
    ["", "12", "abc", "²", "024", "9" * 5000],
    ids=["empty", "12", "letters", "superscript two", "leading zero", "5000 digits"],
)
def test_hours_outside_the_three_periods_get_400(client: Client, hours: str) -> None:
    device, _ = saved_device()

    assert get(client, readings_url(device.pk, hours), device.user) == (
        400,
        {"error": "hours must be 24, 168 or 720."},
    )


@DATABASES
def test_readings_without_a_device_dont_show(client: Client) -> None:
    device, _ = saved_device()
    Esp32Data.objects.create(analog_value=2000, digital_value=1, user=device.user)

    assert get(client, readings_url(device.pk), device.user) == (200, {"readings": []})
    assert get(client, DEVICES_URL, device.user)[1][0]["last_reading_at"] is None


@DATABASES
def test_requests_without_a_token_get_401(client: Client) -> None:
    device, _ = saved_device()

    assert get(client, DEVICES_URL, None)[0] == 401
    assert get(client, readings_url(device.pk), None)[0] == 401


@pytest.mark.access_check
@DATABASES
def test_a_blocked_person_gets_401(client: Client) -> None:
    user_id = saved_person("plants", is_active=False)

    response = client.get(DEVICES_URL, headers=bearer(user_token("plants", user_id)))

    assert response.status_code == 401


@DATABASES
def test_a_plants_api_key_reads_like_the_person_s_token(client: Client) -> None:
    device, _ = saved_device()
    reading(device, hours_ago=1)
    key = bearer(api_key_for({"plants": device.user.pk}))

    devices = client.get(DEVICES_URL, headers=key)
    readings = client.get(readings_url(device.pk, "24"), headers=key)

    assert [d["id"] for d in devices.json()] == [device.pk]
    assert len(readings.json()["readings"]) == 1


@DATABASES
def test_an_api_key_for_another_app_gets_401(client: Client) -> None:
    device, _ = saved_device()
    key = bearer(api_key_for({"cfflch": device.user.pk}))

    assert client.get(DEVICES_URL, headers=key).status_code == 401
    assert client.get(readings_url(device.pk), headers=key).status_code == 401

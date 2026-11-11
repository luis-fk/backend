from collections.abc import Iterator
from dataclasses import dataclass, field
from functools import partial
from typing import Any
from unittest.mock import patch

import httpx
import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from pytest_django import Settings

from plants.models import Esp32Data, Esp32Device, Users
from tests.api_tokens import saved_device

DATABASES = pytest.mark.django_db(databases=["default", "plants_db"])
URL = "/api/esp32/humidity-data"
READING = {"analogValue": 2310, "digitalValue": 1}
INVALID_KEY = {"error": "Missing or invalid device key."}


@dataclass
class FakeOpenWeather:
    """Answers the weather requests with 21.2 °C and 68% humidity and records them.
    With timeout set, it raises a timeout instead."""

    status_code: int = 200
    timeout: bool = False
    # A body to answer with instead of the weather.
    body: bytes | None = None
    requests: list[httpx.Request] = field(default_factory=list)

    def answer(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.timeout:
            raise httpx.ReadTimeout("No answer", request=request)
        if self.body is not None:
            return httpx.Response(self.status_code, content=self.body)
        weather = {"main": {"temp": 21.2, "humidity": 68}}
        return httpx.Response(self.status_code, json=weather)


@pytest.fixture(autouse=True)
def weather_key(settings: Settings) -> None:
    settings.OPEN_WEATHER_API_KEY = "weather-key"


@pytest.fixture
def open_weather() -> Iterator[FakeOpenWeather]:
    """Sends the weather service's requests to a FakeOpenWeather.

    Only the service's own httpx name is replaced: the OpenAI clients, built when
    the first request loads the URLs, check their client against httpx.AsyncClient.
    HTTPError stays the real class, since the service catches it.
    """
    weather = FakeOpenWeather()
    client = partial(httpx.AsyncClient, transport=httpx.MockTransport(weather.answer))
    with patch(
        "plants.api.esp32.service.httpx",
        AsyncClient=client,
        HTTPError=httpx.HTTPError,
    ):
        yield weather


def send_reading(client: Client, body: Any, key: str | None) -> tuple[int, Any]:
    headers = {} if key is None else {"X-Device-Key": key}
    response = client.post(URL, body, content_type="application/json", headers=headers)
    return response.status_code, response.json()


def list_readings(client: Client, key: str) -> tuple[int, Any]:
    response = client.get(URL, headers={"X-Device-Key": key})
    return response.status_code, response.json()


@DATABASES
def test_a_reading_that_is_not_json_gets_400(client: Client) -> None:
    _, key = saved_device()

    assert send_reading(client, "umidade=512", key) == (400, {"error": "Invalid JSON"})


@DATABASES
def test_a_reading_is_saved_with_its_device_its_owner_and_the_weather(
    client: Client, open_weather: FakeOpenWeather
) -> None:
    device, key = saved_device()

    assert send_reading(client, READING, key) == (200, {})

    reading = Esp32Data.objects.get()
    assert (reading.device_id, reading.user_id) == (device.pk, device.user_id)
    assert (reading.analog_value, reading.digital_value) == (2310, 1)
    assert (reading.temperature, reading.humidity) == (21, 68)
    [request] = open_weather.requests
    assert request.url.host == "api.openweathermap.org"
    assert dict(request.url.params) == {
        "lat": "-25.43",
        "lon": "-49.27",
        "units": "metric",
        "appid": "weather-key",
    }


@DATABASES
def test_a_user_id_in_the_body_is_ignored(
    client: Client, open_weather: FakeOpenWeather
) -> None:
    device, key = saved_device()
    other, _ = saved_device("Samambaia")

    assert send_reading(client, {**READING, "userId": other.user_id}, key) == (200, {})

    assert Esp32Data.objects.get().user_id == device.user_id


@DATABASES
@pytest.mark.parametrize(
    "failure",
    [
        "no location",
        "OpenWeather error",
        "timeout",
        "an answer without the weather",
        "an answer that isn't JSON",
        "an empty temperature",
    ],
)
def test_a_reading_is_saved_without_the_weather_when_it_fails(
    client: Client, open_weather: FakeOpenWeather, failure: str
) -> None:
    device, key = saved_device()
    if failure == "no location":
        Users.objects.filter(pk=device.user_id).update(latitude=None, longitude=None)
    elif failure == "OpenWeather error":
        open_weather.status_code = 401
    elif failure == "timeout":
        open_weather.timeout = True
    elif failure == "an answer without the weather":
        open_weather.body = b"{}"
    elif failure == "an answer that isn't JSON":
        open_weather.body = b"<html>maintenance</html>"
    else:
        open_weather.body = b'{"main": {"temp": null, "humidity": 68}}'

    assert send_reading(client, READING, key) == (200, {})

    reading = Esp32Data.objects.get()
    assert (reading.analog_value, reading.temperature, reading.humidity) == (
        2310,
        None,
        None,
    )
    if failure == "no location":
        assert open_weather.requests == []


@DATABASES
@pytest.mark.parametrize("case", ["no header", "unknown key", "inactive device"])
def test_wrong_or_missing_device_keys_get_401(
    client: Client, open_weather: FakeOpenWeather, case: str
) -> None:
    device, key = saved_device()
    sent: str | None = key
    if case == "no header":
        sent = None
    elif case == "unknown key":
        sent = Esp32Device().generate_key()
    else:
        Esp32Device.objects.filter(pk=device.pk).update(active=False)

    assert send_reading(client, READING, sent) == (401, INVALID_KEY)
    assert not Esp32Data.objects.exists()


@DATABASES
@pytest.mark.parametrize("block", ["Active unticked", "plants unticked"])
def test_a_blocked_owner_s_device_gets_401(
    client: Client, open_weather: FakeOpenWeather, block: str
) -> None:
    device, key = saved_device()
    if block == "Active unticked":
        get_user_model().objects.filter(pk=device.user.auth_user_id).update(
            is_active=False
        )
    else:
        Users.objects.filter(pk=device.user_id).update(active=False)

    assert send_reading(client, READING, key) == (401, INVALID_KEY)
    assert not Esp32Data.objects.exists()


@DATABASES
def test_the_device_lists_only_its_own_readings(client: Client) -> None:
    mine, key = saved_device()
    # The owner's other plant, and another person's.
    sibling = Esp32Device(user=mine.user, nickname="Samambaia")
    sibling.generate_key()
    sibling.save()
    other, _ = saved_device("Jiboia")
    for device, raw in [(mine, 2310), (sibling, 1700), (other, 1500), (mine, 2290)]:
        Esp32Data.objects.create(
            analog_value=raw, digital_value=1, user=device.user, device=device
        )

    assert list_readings(client, key) == (
        200,
        [
            {"analogValue": 2310, "digitalValue": 1},
            {"analogValue": 2290, "digitalValue": 1},
        ],
    )


@DATABASES
def test_a_device_without_readings_gets_404(client: Client) -> None:
    _, key = saved_device()

    assert list_readings(client, key) == (404, {"error": "No data found"})


@DATABASES
def test_listing_with_a_wrong_key_gets_401(client: Client) -> None:
    saved_device()

    assert list_readings(client, "dk_wrong") == (401, INVALID_KEY)


@DATABASES
def test_an_odd_location_still_saves_the_reading(
    client: Client, open_weather: FakeOpenWeather
) -> None:
    device, key = saved_device(latitude="-25.43\t", longitude="-49.27")

    assert send_reading(client, READING, key) == (200, {})

    assert Esp32Data.objects.filter(device=device).count() == 1

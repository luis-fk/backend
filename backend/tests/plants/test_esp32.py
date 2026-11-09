from collections.abc import Iterator
from dataclasses import dataclass, field
from functools import partial
from typing import Any
from unittest.mock import patch

import httpx
import pytest
from django.test import Client
from pytest_django import Settings

from plants.models import Esp32Data, Users

DATABASES = pytest.mark.django_db(databases=["default", "plants_db"])
DEVICE = {"X-Device-Key": "device-key"}


@dataclass
class FakeOpenWeather:
    """Answers the weather requests with 18.6 °C and 81% humidity and records them."""

    status_code: int = 200
    requests: list[httpx.Request] = field(default_factory=list)

    def answer(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        weather = {"main": {"temp": 18.6, "humidity": 81}}
        return httpx.Response(self.status_code, json=weather)


@pytest.fixture(autouse=True)
def keys(settings: Settings) -> None:
    settings.ESP32_DEVICE_KEY = "device-key"
    settings.OPEN_WEATHER_API_KEY = "weather-key"


@pytest.fixture
def open_weather() -> Iterator[FakeOpenWeather]:
    """Sends the weather service's requests to a FakeOpenWeather.

    Only the service's own httpx name is replaced: the OpenAI clients, built when
    the first request loads the URLs, check their client against httpx.AsyncClient.
    """
    weather = FakeOpenWeather()
    client = partial(httpx.AsyncClient, transport=httpx.MockTransport(weather.answer))
    with patch("plants.api.esp32.service.httpx", AsyncClient=client):
        yield weather


def send_reading(client: Client, body: Any) -> tuple[int, Any]:
    response = client.post(
        "/api/esp32/humidity-data",
        body,
        content_type="application/json",
        headers=DEVICE,
    )
    return response.status_code, response.json()


def list_readings(client: Client) -> tuple[int, Any]:
    response = client.get("/api/esp32/humidity-data", headers=DEVICE)
    return response.status_code, response.json()


def reading_from(user_id: int) -> dict[str, int]:
    return {"analogValue": 512, "digitalValue": 1, "userId": user_id}


def test_a_reading_that_is_not_json_gets_400(client: Client) -> None:
    assert send_reading(client, "umidade=512") == (400, {"error": "Invalid JSON"})


@DATABASES
def test_a_reading_is_saved_with_the_weather_where_the_user_lives(
    client: Client, open_weather: FakeOpenWeather
) -> None:
    user = Users.objects.create(auth_user_id=1, latitude="-25.43", longitude="-49.27")

    answer = send_reading(client, reading_from(user.id))

    assert answer == (200, {})
    reading = Esp32Data.objects.get()
    assert (reading.analog_value, reading.digital_value) == (512, 1)
    assert (reading.temperature, reading.humidity, reading.user_id) == (19, 81, user.id)
    [request] = open_weather.requests
    assert request.url.host == "api.openweathermap.org"
    assert dict(request.url.params) == {
        "lat": "-25.43",
        "lon": "-49.27",
        "units": "metric",
        "appid": "weather-key",
    }


@DATABASES
def test_a_reading_from_an_unknown_user_is_refused_without_asking_for_the_weather(
    client: Client, open_weather: FakeOpenWeather
) -> None:
    answer = send_reading(client, reading_from(999))

    assert answer == (400, {"error": "User not found"})
    assert open_weather.requests == []
    assert not Esp32Data.objects.exists()


@DATABASES
def test_a_reading_is_not_saved_when_the_weather_fails(
    client: Client, open_weather: FakeOpenWeather
) -> None:
    user = Users.objects.create(auth_user_id=1, latitude="-25.43", longitude="-49.27")
    open_weather.status_code = 401

    answer = send_reading(client, reading_from(user.id))

    assert answer == (400, {"error": "Error fetching weather data"})
    assert not Esp32Data.objects.exists()


@DATABASES
def test_the_readings_are_listed_with_the_names_the_esp32_uses(client: Client) -> None:
    user = Users.objects.create(auth_user_id=1)
    Esp32Data.objects.create(analog_value=512, digital_value=1, user=user)

    assert list_readings(client) == (200, [reading_from(user.id)])


@DATABASES
def test_without_readings_the_list_gets_404(client: Client) -> None:
    assert list_readings(client) == (404, {"error": "No data found"})

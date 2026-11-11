from collections.abc import Callable, Iterator
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.http import HttpResponseBase
from django.test import Client

from plants.api.chatbot.routes import ChatBotApi
from plants.models import ChatHistory, Esp32Data
from tests.api_tokens import (
    api_key,
    bearer,
    login_token,
    make_token,
    saved_device,
    saved_person,
    unknown_api_key,
    user_token,
)

Send = Callable[[Client, int, dict[str, str]], HttpResponseBase]


def get_history(
    client: Client, user_id: int, headers: dict[str, str]
) -> HttpResponseBase:
    return client.get(f"/api/chat-history/{user_id}/", headers=headers)


def send_message(
    client: Client, user_id: int, headers: dict[str, str]
) -> HttpResponseBase:
    return client.post(
        "/api/chatbot/message",
        {"user_id": user_id, "message": "Olá"},
        content_type="application/json",
        headers=headers,
    )


def find_user(client: Client, headers: dict[str, str]) -> HttpResponseBase:
    return client.get("/api/plants/users/ana/", headers=headers)


def send_reading(client: Client, headers: dict[str, str]) -> HttpResponseBase:
    return client.post(
        "/api/esp32/humidity-data",
        {"analogValue": 512, "digitalValue": 1, "userId": 7},
        content_type="application/json",
        headers=headers,
    )


@pytest.mark.parametrize("send", [get_history, send_message])
def test_requests_without_a_token_get_401(client: Client, send: Send) -> None:
    assert send(client, 7, {}).status_code == 401


@pytest.mark.parametrize("send", [get_history, send_message])
def test_tokens_for_another_app_get_401(client: Client, send: Send) -> None:
    headers = bearer(user_token("political-culture", "7"))

    assert send(client, 7, headers).status_code == 401


@pytest.mark.parametrize("send", [get_history, send_message])
def test_tokens_for_another_user_get_403(client: Client, send: Send) -> None:
    headers = bearer(user_token("plants", "7"))

    assert send(client, 8, headers).status_code == 403


def test_auth_errors_use_the_api_error_format(client: Client) -> None:
    unauthenticated = client.get("/api/chat-history/7/")
    forbidden = client.get(
        "/api/chat-history/8/", headers=bearer(user_token("plants", "7"))
    )

    assert unauthenticated.json() == {"error": "Missing or invalid token."}
    assert unauthenticated["WWW-Authenticate"] == "Bearer"
    assert forbidden.json() == {"error": "The token belongs to another user."}


def test_users_read_their_own_chat_history(client: Client) -> None:
    with patch.object(ChatHistory.objects, "filter") as history:
        response = get_history(client, 7, bearer(user_token("plants", "7")))

    assert response.status_code == 200
    history.assert_called_once_with(user_id="7")


def test_users_send_their_own_messages(client: Client) -> None:
    with patch.object(ChatBotApi, "llm") as llm:
        llm.process_message.return_value.data = {"role": "ai", "message": "Oi"}
        response = send_message(client, 7, bearer(user_token("plants", "7")))

    assert response.status_code == 200
    llm.process_message.assert_called_once_with(message="Olá", user_id=7)


@pytest.fixture
def app_data() -> Iterator[None]:
    """The chat history and the chatbot, without a database."""
    with (
        patch.object(ChatHistory.objects, "filter"),
        patch.object(ChatBotApi, "llm") as llm,
    ):
        llm.process_message.return_value.data = {"role": "ai", "message": "Oi"}
        yield


@pytest.mark.django_db
@pytest.mark.usefixtures("app_data")
@pytest.mark.parametrize("send", [get_history, send_message])
def test_api_keys_act_as_their_user(client: Client, send: Send) -> None:
    assert send(client, 7, bearer(api_key("plants", 7))).status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize("send", [get_history, send_message])
def test_api_keys_for_another_user_get_403(client: Client, send: Send) -> None:
    assert send(client, 8, bearer(api_key("plants", 7))).status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize("send", [get_history, send_message])
def test_api_keys_for_another_app_get_401(client: Client, send: Send) -> None:
    headers = bearer(api_key("political-culture", 7))

    assert send(client, 7, headers).status_code == 401


@pytest.mark.django_db
@pytest.mark.parametrize("send", [get_history, send_message])
def test_inactive_api_keys_get_401(client: Client, send: Send) -> None:
    headers = bearer(api_key("plants", 7, active=False))

    assert send(client, 7, headers).status_code == 401


@pytest.mark.django_db
@pytest.mark.parametrize("send", [get_history, send_message])
def test_unknown_api_keys_get_401(client: Client, send: Send) -> None:
    assert send(client, 7, bearer(unknown_api_key())).status_code == 401


def test_the_login_lookup_without_a_token_gets_401(client: Client) -> None:
    assert find_user(client, {}).status_code == 401


@pytest.mark.parametrize(
    ("app", "purpose"),
    [("plants", "user"), ("cfflch", "login")],
    ids=["user token", "another app's login token"],
)
def test_the_login_lookup_with_another_token_gets_401(
    client: Client, app: str, purpose: str
) -> None:
    headers = bearer(make_token(sub="7", app=app, purpose=purpose))

    assert find_user(client, headers).status_code == 401


def test_the_login_lookup_runs_with_a_login_token(client: Client) -> None:
    AuthUser = get_user_model()
    with patch.object(AuthUser.objects, "using") as using:
        using.return_value.get.side_effect = AuthUser.DoesNotExist
        response = find_user(client, bearer(login_token("plants")))

    assert response.status_code == 404
    using.return_value.get.assert_called_once_with(username="ana", is_active=True)


@pytest.mark.django_db(databases=["default", "plants_db"])
@pytest.mark.parametrize("key", ["", "dk_wrong"], ids=["no key", "wrong key"])
def test_esp32_requests_without_a_device_key_get_401(client: Client, key: str) -> None:
    saved_device()
    headers = {"X-Device-Key": key} if key else {}

    assert send_reading(client, headers).status_code == 401
    assert client.get("/api/esp32/humidity-data", headers=headers).status_code == 401


@pytest.mark.django_db(databases=["default", "plants_db"])
def test_the_device_key_lets_the_esp32_in(client: Client) -> None:
    _, key = saved_device()

    response = client.post(
        "/api/esp32/humidity-data",
        {},
        content_type="application/json",
        headers={"X-Device-Key": key},
    )

    # Past the key check, the empty reading fails validation.
    assert response.status_code == 400


@pytest.mark.django_db(databases=["default", "plants_db"])
def test_a_valid_reading_is_saved(client: Client) -> None:
    device, key = saved_device()
    weather = SimpleNamespace(error_message=None, temperature=25.0, humidity=60)

    with (
        patch(
            "plants.api.esp32.routes.fetch_weather_data",
            AsyncMock(return_value=weather),
        ),
        patch.object(Esp32Data.objects, "acreate", AsyncMock()) as acreate,
    ):
        response = send_reading(client, {"X-Device-Key": key})

    assert response.status_code == 200
    acreate.assert_awaited_once_with(
        analog_value=512,
        digital_value=1,
        temperature=25.0,
        humidity=60,
        device=device,
        user_id=device.user_id,
    )


@pytest.mark.access_check
@pytest.mark.django_db(databases=["default", "plants_db"])
@pytest.mark.parametrize(
    ("is_active", "active", "status"),
    [(True, True, 200), (False, True, 401), (True, False, 401)],
    ids=["can use plants", "Active unticked", "plants unticked"],
)
def test_only_people_who_can_use_plants_get_in(
    client: Client, is_active: bool, active: bool, status: int
) -> None:
    user_id = saved_person("plants", is_active=is_active, active=active)

    response = get_history(client, int(user_id), bearer(user_token("plants", user_id)))

    assert response.status_code == status

import asyncio
from typing import Any

import pytest
from channels.layers import get_channel_layer
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from pytest_django import Settings

from political_culture.api.messages.routing import websocket_urlpatterns
from tests.api_tokens import api_key, make_token, saved_person, user_token

APP = "political-culture"


# The consumers check the person in the database when a socket opens, through
# database_sync_to_async, which also tidies its thread's connections: every test
# here may touch the database.
pytestmark = pytest.mark.django_db(databases=["default", "political_culture_db"])


@pytest.fixture(autouse=True)
def in_memory_channel_layer(settings: Settings) -> None:
    """The consumer joins a group on the channel layer; keep it off Redis."""
    settings.CHANNEL_LAYERS = {
        "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}
    }


def open_chat_socket(user_id: int, subprotocols: list[str]) -> tuple[bool, Any]:
    """Returns (True, the accepted subprotocol) or (False, the close code)."""

    async def connect() -> tuple[bool, Any]:
        communicator = WebsocketCommunicator(
            URLRouter(websocket_urlpatterns),
            f"/ws/chat/{user_id}",
            subprotocols=subprotocols,
        )
        connected, detail = await communicator.connect()
        await communicator.disconnect()
        return connected, detail

    return asyncio.run(connect())


def test_the_chat_socket_accepts_the_users_token() -> None:
    connected, subprotocol = open_chat_socket(7, ["bearer", user_token(APP, "7")])

    assert connected
    assert subprotocol == "bearer"


def test_the_chat_socket_rejects_a_connection_without_a_token() -> None:
    connected, _ = open_chat_socket(7, [])

    assert not connected


@pytest.mark.parametrize(
    "claims",
    [
        {"sub": "8", "app": APP, "purpose": "user"},
        {"sub": "7", "app": "plants", "purpose": "user"},
        {"app": APP, "purpose": "login"},
    ],
    ids=["another user", "another app", "login token"],
)
def test_the_chat_socket_rejects_other_tokens(claims: dict[str, str]) -> None:
    connected, _ = open_chat_socket(7, ["bearer", make_token(**claims)])

    assert not connected


def test_the_chat_socket_rejects_an_api_key() -> None:
    connected, _ = open_chat_socket(7, ["bearer", api_key(APP, 7)])

    assert not connected


ANSWER = {"type": "chat.message", "message": {"role": "ai", "message": "Olá!"}}


def users_chat_socket() -> WebsocketCommunicator:
    """A client for user 7's chat socket, with their token."""
    return WebsocketCommunicator(
        URLRouter(websocket_urlpatterns),
        "/ws/chat/7",
        subprotocols=["bearer", user_token(APP, "7")],
    )


def test_the_chat_socket_relays_the_users_answers() -> None:
    async def scenario() -> Any:
        communicator = users_chat_socket()
        await communicator.connect()
        await get_channel_layer().group_send("chat_7", ANSWER)
        received = await communicator.receive_json_from()
        await communicator.disconnect()
        return received

    assert asyncio.run(scenario()) == {"role": "ai", "message": "Olá!"}


def test_the_chat_socket_gets_nothing_meant_for_another_user() -> None:
    async def scenario() -> bool:
        communicator = users_chat_socket()
        await communicator.connect()
        await get_channel_layer().group_send("chat_8", ANSWER)
        got_nothing: bool = await communicator.receive_nothing()
        await communicator.disconnect()
        return got_nothing

    assert asyncio.run(scenario())


@pytest.mark.access_check
@pytest.mark.django_db(databases=["default", "political_culture_db"], transaction=True)
@pytest.mark.parametrize(
    ("is_active", "active", "connects"),
    [(True, True, True), (False, True, False), (True, False, False)],
    ids=["can use the app", "Active unticked", "app unticked"],
)
def test_the_chat_socket_lets_in_only_people_who_can_use_the_app(
    is_active: bool, active: bool, connects: bool
) -> None:
    user_id = saved_person(APP, is_active=is_active, active=active)

    connected, _ = open_chat_socket(int(user_id), ["bearer", user_token(APP, user_id)])

    assert connected is connects

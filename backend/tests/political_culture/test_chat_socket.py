import asyncio
from typing import Any

import pytest
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from pytest_django import Settings

from political_culture.api.messages.routing import websocket_urlpatterns
from tests.api_tokens import make_token, user_token

APP = "political-culture"


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

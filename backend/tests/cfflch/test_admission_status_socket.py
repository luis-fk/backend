import asyncio
from typing import Any

import pytest
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from pytest_django import Settings

from cfflch.api.admission_status.routing import websocket_urlpatterns
from tests.api_tokens import api_key, login_token, user_token


@pytest.fixture(autouse=True)
def in_memory_channel_layer(settings: Settings) -> None:
    """The consumer joins a group on the channel layer; keep it off Redis."""
    settings.CHANNEL_LAYERS = {
        "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}
    }


def open_status_socket(subprotocols: list[str]) -> tuple[bool, Any]:
    """Returns (True, the accepted subprotocol) or (False, the close code)."""

    async def connect() -> tuple[bool, Any]:
        communicator = WebsocketCommunicator(
            URLRouter(websocket_urlpatterns),
            "/ws/cfflch/admission-status/abc",
            subprotocols=subprotocols,
        )
        connected, detail = await communicator.connect()
        await communicator.disconnect()
        return connected, detail

    return asyncio.run(connect())


def test_the_status_socket_accepts_any_cfflch_user() -> None:
    connected, subprotocol = open_status_socket(["bearer", user_token("cfflch", "8")])

    assert connected
    assert subprotocol == "bearer"


def test_the_status_socket_rejects_a_connection_without_a_token() -> None:
    connected, _ = open_status_socket([])

    assert not connected


def test_the_status_socket_rejects_another_apps_token() -> None:
    connected, _ = open_status_socket(["bearer", user_token("plants")])

    assert not connected


def test_the_status_socket_rejects_a_login_token() -> None:
    connected, _ = open_status_socket(["bearer", login_token("cfflch")])

    assert not connected


@pytest.mark.django_db
def test_the_status_socket_rejects_an_api_key() -> None:
    connected, _ = open_status_socket(["bearer", api_key("cfflch")])

    assert not connected

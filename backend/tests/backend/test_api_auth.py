import time
from typing import Any

import jwt
import pytest
from django.http import HttpRequest
from django.test import RequestFactory
from pytest_django import DjangoAssertNumQueries, Settings
from rest_framework.exceptions import PermissionDenied

from api_keys.models import ApiKey
from backend.api_auth import (
    InvalidToken,
    has_valid_device_key,
    require_same_user,
    require_user_token,
    websocket_user_id,
)
from tests.api_tokens import api_key, bearer, make_token, user_token


def request_with(headers: dict[str, str]) -> HttpRequest:
    return RequestFactory().get("/", headers=headers)


def test_a_user_token_gives_its_user_id() -> None:
    request = request_with(bearer(user_token("plants", "7")))

    assert require_user_token(request, "plants") == "7"


@pytest.mark.parametrize(
    "claims",
    [
        {"sub": "7", "app": "cfflch", "purpose": "user"},
        {"app": "plants", "purpose": "login"},
        {"app": "plants", "purpose": "user"},
        {"sub": "7", "app": "plants", "purpose": "user", "exp": None},
        {"sub": "7", "app": "plants", "purpose": "user", "exp": 1_700_000_000},
    ],
    ids=["another app", "login token", "no user id", "no expiry", "expired"],
)
def test_tokens_with_the_wrong_claims_get_401(claims: dict[str, Any]) -> None:
    request = request_with(bearer(make_token(**claims)))

    with pytest.raises(InvalidToken):
        require_user_token(request, "plants")


@pytest.mark.parametrize(
    "headers",
    [{}, bearer(""), bearer("not-a-jwt")],
    ids=["no header", "empty token", "malformed token"],
)
def test_requests_without_a_token_get_401(headers: dict[str, str]) -> None:
    with pytest.raises(InvalidToken):
        require_user_token(request_with(headers), "plants")


def test_tokens_signed_with_another_secret_get_401() -> None:
    now = int(time.time())
    claims = {"sub": "7", "app": "plants", "purpose": "user", "exp": now + 60}
    token = jwt.encode(
        claims, "another-secret-with-32-or-more-chars", algorithm="HS256"
    )

    with pytest.raises(InvalidToken):
        require_user_token(request_with(bearer(token)), "plants")


def test_a_token_issued_a_few_seconds_ahead_is_accepted() -> None:
    token = make_token(sub="7", app="plants", purpose="user", iat=int(time.time()) + 5)

    assert require_user_token(request_with(bearer(token)), "plants") == "7"


@pytest.mark.django_db
def test_an_api_key_gives_its_user_id_and_records_its_use() -> None:
    request = request_with(bearer(api_key("plants", 7)))
    assert ApiKey.objects.get().last_used_at is None

    assert require_user_token(request, "plants") == "7"
    assert ApiKey.objects.get().last_used_at is not None


def test_another_users_id_gets_403() -> None:
    require_same_user("7", 7)
    require_same_user("7", "7")

    with pytest.raises(PermissionDenied):
        require_same_user("7", 8)


def test_the_device_key_must_match(settings: Settings) -> None:
    settings.ESP32_DEVICE_KEY = "device-key"

    assert has_valid_device_key(request_with({"X-Device-Key": "device-key"}))
    assert not has_valid_device_key(request_with({"X-Device-Key": "another-key"}))
    assert not has_valid_device_key(request_with({}))


def test_an_empty_device_key_setting_matches_nothing(settings: Settings) -> None:
    settings.ESP32_DEVICE_KEY = ""

    assert not has_valid_device_key(request_with({}))
    assert not has_valid_device_key(request_with({"X-Device-Key": ""}))


def test_websocket_tokens_come_as_the_bearer_subprotocols() -> None:
    token = user_token("cfflch", "7")

    assert websocket_user_id({"subprotocols": ["bearer", token]}, "cfflch") == "7"
    assert websocket_user_id({"subprotocols": ["bearer", token]}, "plants") is None
    assert websocket_user_id({"subprotocols": [token]}, "cfflch") is None
    assert websocket_user_id({"subprotocols": ["bearer", token, "x"]}, "cfflch") is None
    assert websocket_user_id({"subprotocols": []}, "cfflch") is None


@pytest.mark.django_db
def test_websockets_refuse_api_keys_without_a_query(
    django_assert_num_queries: DjangoAssertNumQueries,
) -> None:
    scope = {"subprotocols": ["bearer", api_key("cfflch", 7)]}

    with django_assert_num_queries(0):
        assert websocket_user_id(scope, "cfflch") is None

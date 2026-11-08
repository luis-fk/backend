"""Token, API key and device key checks for plants, political_culture and cfflch.

The frontend signs HS256 JWTs with API_TOKEN_SECRET:
- a user token, {sub: the app's user id, app, purpose: "user"}, for a logged-in user;
- a login token, {app, purpose: "login"}, for the login lookup by name.
The app keys are "plants", "political-culture" and "cfflch".

Over HTTP, an active API key (the api_keys app) works wherever a user token does, as
its user in its app. The WebSockets take only user tokens.
"""

import hmac
from datetime import timedelta
from typing import Any

import jwt
from django.conf import settings
from django.http import HttpRequest
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import APIException, PermissionDenied

from api_keys.models import KEY_START, ApiKey, hash_key

ALGORITHM = "HS256"
# The frontend's clock may run a little ahead, and PyJWT rejects a token issued in
# the future.
CLOCK_LEEWAY = timedelta(seconds=10)


class InvalidToken(APIException):
    """A 401 for a missing or invalid token.

    DRF's own NotAuthenticated would become a 403 here: DRF answers 401 only when the
    view's first authentication class names a scheme, and this API uses none (see
    REST_FRAMEWORK in settings.py).
    """

    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = {"error": "Missing or invalid token."}
    auth_header = "Bearer"


def require_user_token(request: HttpRequest, app: str) -> str:
    """For DRF views: the user id of the request's user token or API key for app,
    or a 401."""
    user_id = _request_user_id(request, app)
    if user_id is None:
        raise InvalidToken()
    return user_id


def require_same_user(token_user_id: str, user_id: object) -> None:
    """For DRF views: a 403 when the user id in the path or body is not the token's."""
    if str(user_id) != token_user_id:
        raise PermissionDenied({"error": "The token belongs to another user."})


def require_login_token(request: HttpRequest, app: str) -> None:
    """For DRF views: a 401 unless the request has a login token for app."""
    if _claims(_bearer_token(request), app, "login") is None:
        raise InvalidToken()


def has_valid_user_token(request: HttpRequest, app: str) -> bool:
    """For plain Django views, which don't turn DRF errors into responses.

    An API key takes a database query, so an async view calls this through
    sync_to_async.
    """
    return _request_user_id(request, app) is not None


def has_valid_device_key(request: HttpRequest) -> bool:
    """Whether X-Device-Key is ESP32_DEVICE_KEY. An empty key never matches."""
    key = request.headers.get("X-Device-Key", "")
    # compare_digest takes as long for any wrong key, so the key can't be guessed
    # one character at a time.
    return key != "" and hmac.compare_digest(
        key.encode(), settings.ESP32_DEVICE_KEY.encode()
    )


def websocket_user_id(scope: dict[str, Any], app: str) -> str | None:
    """The user id of a user token sent as the subprotocols ["bearer", token].

    A browser can't set headers on a WebSocket, and a token in the query string
    would end up in access logs.
    """
    match scope.get("subprotocols"):
        case ["bearer", token]:
            return _user_id(token, app)
        case _:
            return None


def _bearer_token(request: HttpRequest) -> str:
    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    return token if scheme.lower() == "bearer" else ""


def _request_user_id(request: HttpRequest, app: str) -> str | None:
    token = _bearer_token(request)
    if token.startswith(KEY_START):
        return _api_key_user_id(token, app)
    return _user_id(token, app)


def _api_key_user_id(key: str, app: str) -> str | None:
    """The user id of an active API key for app, or None. Records the key's use."""
    api_key = ApiKey.objects.filter(
        key_hash=hash_key(key), app=app, active=True
    ).first()
    if api_key is None:
        return None
    api_key.last_used_at = timezone.now()
    api_key.save(update_fields=["last_used_at"])
    return str(api_key.user_id)


def _user_id(token: str, app: str) -> str | None:
    claims = _claims(token, app, "user")
    user_id: str | None = claims.get("sub") if claims else None
    return user_id


def _claims(token: str, app: str, purpose: str) -> dict[str, Any] | None:
    """The claims of a valid, unexpired token for app and purpose, or None."""
    try:
        claims: dict[str, Any] = jwt.decode(
            token,
            settings.API_TOKEN_SECRET,
            algorithms=[ALGORITHM],
            options={"require": ["exp"]},
            leeway=CLOCK_LEEWAY,
        )
    except jwt.InvalidTokenError:
        return None
    if claims.get("app") != app or claims.get("purpose") != purpose:
        return None
    return claims

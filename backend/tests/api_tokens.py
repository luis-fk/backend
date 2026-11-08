"""Tokens signed like the frontend's, and API keys (see backend/api_auth.py)."""

import time
from typing import Any

import jwt
from django.conf import settings

from api_keys.models import ApiKey


def make_token(**claims: Any) -> str:
    now = int(time.time())
    return jwt.encode(
        {"iat": now, "exp": now + 60, **claims},
        settings.API_TOKEN_SECRET,
        algorithm="HS256",
    )


def user_token(app: str, user_id: str = "7") -> str:
    return make_token(sub=user_id, app=app, purpose="user")


def login_token(app: str) -> str:
    return make_token(app=app, purpose="login")


def api_key(app: str, user_id: int = 7, active: bool = True) -> str:
    """Saves an API key and returns it; the test needs the django_db mark."""
    row = ApiKey(name="test", app=app, user_id=user_id, active=active)
    key = row.generate_key()
    row.save()
    return key


def unknown_api_key() -> str:
    """A key that looks right but was never saved."""
    return ApiKey().generate_key()


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}

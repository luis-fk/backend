"""Tokens signed the way the frontend signs them (see backend/api_auth.py)."""

import time
from typing import Any

import jwt
from django.conf import settings


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


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}

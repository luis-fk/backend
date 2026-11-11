"""Tokens signed like the frontend's, and API keys (see backend/api_auth.py)."""

import time
from typing import Any

import jwt
from django.conf import settings
from django.contrib.auth import get_user_model

from api_keys.app_users import users_model
from api_keys.models import ApiKey
from plants.models import Esp32Device, Users


def make_token(**claims: Any) -> str:
    now = int(time.time())
    return jwt.encode(
        {"iat": now, "exp": now + 60, **claims},
        settings.API_TOKEN_SECRET,
        algorithm="HS256",
    )


def user_token(app: str, user_id: str = "7") -> str:
    return make_token(sub=user_id, app=app, purpose="user")


def saved_person(app: str, *, is_active: bool = True, active: bool = True) -> str:
    """Saves an auth user with is_active and their row in app's Users with active,
    and returns their id in app; the test needs the default and app databases."""
    auth_user = get_user_model().objects.create_user(
        username=f"person-in-{app}", is_active=is_active
    )
    row = users_model(app)._default_manager.create(
        auth_user_id=auth_user.pk, active=active
    )
    return str(row.pk)


def login_token(app: str) -> str:
    return make_token(app=app, purpose="login")


def api_key(app: str, user_id: int = 7, active: bool = True) -> str:
    """Saves an API key for one app and returns it; the test needs the django_db
    mark."""
    return api_key_for({app: user_id}, active)


def api_key_for(users: dict[str, int], active: bool = True) -> str:
    """Saves an API key for several apps, with the person's id in each, and
    returns it; the test needs the django_db mark."""
    row = ApiKey(name="test", users=users, active=active)
    key = row.generate_key()
    row.save()
    return key


def unknown_api_key() -> str:
    """A key that looks right but was never saved."""
    return ApiKey().generate_key()


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def saved_device(nickname: str = "Manjericão", **owner: Any) -> tuple[Esp32Device, str]:
    """Saves a person who can use plants and lives in Curitiba, with a device of
    theirs; owner overrides fields of their plants Users row. Returns the device and
    its key; the test needs the default and plants databases."""
    # A number in the name, so two people can have plants with the same nickname.
    number = get_user_model().objects.count() + 1
    person = get_user_model().objects.create_user(username=f"owner-{number}")
    user = Users.objects.create(
        auth_user_id=person.pk,
        **{"latitude": "-25.43", "longitude": "-49.27", **owner},
    )
    device = Esp32Device(user=user, nickname=nickname)
    key = device.generate_key()
    device.save()
    return device, key

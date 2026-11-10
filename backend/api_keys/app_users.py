from collections.abc import Iterable

from django.apps import apps
from django.db.models import Model

# Each app's Users table, looked up by name so this app doesn't import the others.
# A person is an auth user, and their row in an app's Users points to them by
# auth_user_id, since each app has its own database.
USERS_MODELS = {
    "plants": "plants.Users",
    "political-culture": "political_culture.Users",
    "cfflch": "cfflch.Users",
}


def users_model(app: str) -> type[Model]:
    return apps.get_model(USERS_MODELS[app])


def apps_of(auth_user_id: int) -> list[str]:
    """The apps the person is in."""
    return [
        app
        for app in USERS_MODELS
        if users_model(app)._default_manager.filter(auth_user_id=auth_user_id).exists()
    ]


def ids_in_apps(auth_user_id: int, chosen: Iterable[str]) -> dict[str, int]:
    """The person's id in each of the chosen apps they are in."""
    ids = {}
    for app in chosen:
        pk = (
            users_model(app)
            ._default_manager.filter(auth_user_id=auth_user_id)
            .values_list("pk", flat=True)
            .first()
        )
        if pk is not None:
            ids[app] = pk
    return ids


def add_to_apps(auth_user_id: int, chosen: Iterable[str]) -> None:
    for app in chosen:
        users_model(app)._default_manager.get_or_create(auth_user_id=auth_user_id)

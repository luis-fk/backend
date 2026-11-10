from collections.abc import Iterable

from django.apps import apps
from django.contrib.auth import get_user_model
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
    """The apps the person can use."""
    return [
        app
        for app in USERS_MODELS
        if users_model(app)
        ._default_manager.filter(auth_user_id=auth_user_id, active=True)
        .exists()
    ]


def ids_in_apps(auth_user_id: int, chosen: Iterable[str]) -> dict[str, int]:
    """The person's id in each of the chosen apps they can use."""
    ids = {}
    for app in chosen:
        pk = (
            users_model(app)
            ._default_manager.filter(auth_user_id=auth_user_id, active=True)
            .values_list("pk", flat=True)
            .first()
        )
        if pk is not None:
            ids[app] = pk
    return ids


def set_apps(auth_user_id: int, chosen: Iterable[str]) -> None:
    """Lets the person use the chosen apps and blocks them in the others. A blocked
    person keeps their row in the app, and with it their data there."""
    ticked = set(chosen)
    for app in USERS_MODELS:
        users = users_model(app)._default_manager
        if app in ticked:
            users.update_or_create(auth_user_id=auth_user_id, defaults={"active": True})
        else:
            users.filter(auth_user_id=auth_user_id).update(active=False)


def can_use(app: str, user_id: str | int) -> bool:
    """Whether the person with this id in the app's Users can still use the app:
    their row there and their auth user are both active."""
    auth_user_id = (
        users_model(app)
        ._default_manager.filter(pk=user_id, active=True)
        .values_list("auth_user_id", flat=True)
        .first()
    )
    return (
        auth_user_id is not None
        and get_user_model()
        ._default_manager.filter(pk=auth_user_id, is_active=True)
        .exists()
    )

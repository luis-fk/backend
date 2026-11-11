from typing import Any

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from political_culture.models import Users
from tests.api_tokens import bearer, login_token

DATABASES = pytest.mark.django_db(databases=["default", "political_culture_db"])


def find_user(client: Client, name: str) -> tuple[int, Any]:
    response = client.get(
        f"/api/political-culture/users/{name}",
        headers=bearer(login_token("political-culture")),
    )
    return response.status_code, response.json()


@DATABASES
def test_the_login_lookup_answers_the_political_culture_user_id(client: Client) -> None:
    auth_user = get_user_model().objects.create_user(username="fulano")
    # An id unlike the auth user's, so the answer can only be the app's one.
    app_user = Users.objects.create(id=auth_user.id + 1, auth_user_id=auth_user.id)

    assert find_user(client, "fulano") == (200, {"id": app_user.id})


@DATABASES
def test_a_login_without_a_political_culture_user_gets_404(client: Client) -> None:
    get_user_model().objects.create_user(username="fulano")

    assert find_user(client, "fulano") == (404, {"error": "User not found."})


@DATABASES
@pytest.mark.parametrize(
    ("is_active", "active"),
    [(False, True), (True, False)],
    ids=["Active unticked", "political culture unticked"],
)
def test_a_blocked_person_gets_404(
    client: Client, is_active: bool, active: bool
) -> None:
    auth_user = get_user_model().objects.create_user(
        username="fulano", is_active=is_active
    )
    Users.objects.create(auth_user_id=auth_user.id, active=active)

    assert find_user(client, "fulano") == (404, {"error": "User not found."})

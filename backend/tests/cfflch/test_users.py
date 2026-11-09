from typing import Any

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from cfflch.models import Users
from tests.api_tokens import bearer, login_token

DATABASES = pytest.mark.django_db(databases=["default", "cfflch_db"])


def find_user(client: Client, name: str) -> tuple[int, Any]:
    response = client.get(
        f"/api/cfflch/users/{name}", headers=bearer(login_token("cfflch"))
    )
    return response.status_code, response.json()


@DATABASES
def test_the_login_lookup_answers_the_cfflch_user_id(client: Client) -> None:
    auth_user = get_user_model().objects.create_user(username="fulano")
    # An id unlike the auth user's, so the answer can only be the cfflch one.
    cfflch_user = Users.objects.create(id=auth_user.id + 1, auth_user_id=auth_user.id)

    assert find_user(client, "fulano") == (200, {"id": cfflch_user.id})


@DATABASES
def test_a_login_without_a_cfflch_user_gets_404(client: Client) -> None:
    get_user_model().objects.create_user(username="fulano")

    assert find_user(client, "fulano") == (404, {"error": "User not found."})

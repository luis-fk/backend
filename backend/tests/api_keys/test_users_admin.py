from typing import Any

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from cfflch.models import Users as CfflchUsers
from plants.models import Users as PlantsUsers
from political_culture.models import Users as PoliticalCultureUsers

DATABASES = pytest.mark.django_db(
    databases=["default", "plants_db", "political_culture_db", "cfflch_db"]
)
USERS_URL = "/admin/auth/user/"


def change_data(username: str, **changes: Any) -> dict[str, Any]:
    """The fields the user change form requires."""
    return {
        "username": username,
        "date_joined_0": "2026-11-10",
        "date_joined_1": "12:00:00",
        "is_active": "on",
        **changes,
    }


@DATABASES
def test_a_new_user_joins_the_apps_ticked_on_the_form(admin_client: Client) -> None:
    response = admin_client.post(
        f"{USERS_URL}add/",
        {
            "username": "maria",
            "usable_password": "true",
            "password1": "a-Long-pass-1234",
            "password2": "a-Long-pass-1234",
            "apps": ["plants", "cfflch"],
        },
    )

    assert response.status_code == 302
    maria = get_user_model().objects.get(username="maria")
    assert PlantsUsers.objects.filter(auth_user_id=maria.pk).exists()
    assert CfflchUsers.objects.filter(auth_user_id=maria.pk).exists()
    assert not PoliticalCultureUsers.objects.filter(auth_user_id=maria.pk).exists()


@DATABASES
def test_the_user_page_shows_the_apps_and_adds_new_ones_without_removing_any(
    admin_client: Client,
) -> None:
    maria = get_user_model().objects.create_user(username="maria")
    PlantsUsers.objects.create(auth_user_id=maria.pk)
    url = f"{USERS_URL}{maria.pk}/change/"

    form = admin_client.get(url).context["adminform"].form
    assert form["apps"].initial == ["plants"]

    response = admin_client.post(
        url, change_data("maria", apps=["plants", "political-culture"])
    )
    assert response.status_code == 302
    assert PoliticalCultureUsers.objects.filter(auth_user_id=maria.pk).exists()

    # Unticking doesn't remove anyone: that would delete their data in the app.
    admin_client.post(url, change_data("maria", apps=[]))
    assert PlantsUsers.objects.filter(auth_user_id=maria.pk).exists()
    assert PoliticalCultureUsers.objects.filter(auth_user_id=maria.pk).exists()


@DATABASES
def test_the_users_list_shows_each_persons_apps(admin_client: Client) -> None:
    maria = get_user_model().objects.create_user(username="maria")
    PlantsUsers.objects.create(auth_user_id=maria.pk)
    CfflchUsers.objects.create(auth_user_id=maria.pk)

    page = admin_client.get(USERS_URL).content.decode()

    assert "plants, cfflch" in page

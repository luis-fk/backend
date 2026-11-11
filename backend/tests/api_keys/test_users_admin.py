from typing import Any

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
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
def test_unticking_an_app_blocks_the_person_there_and_keeps_their_row(
    admin_client: Client,
) -> None:
    maria = get_user_model().objects.create_user(username="maria")
    in_plants = PlantsUsers.objects.create(auth_user_id=maria.pk)
    url = f"{USERS_URL}{maria.pk}/change/"

    form = admin_client.get(url).context["adminform"].form
    assert form["apps"].initial == ["plants"]

    admin_client.post(url, change_data("maria", apps=["political-culture"]))

    assert not PlantsUsers.objects.get(pk=in_plants.pk).active
    assert PoliticalCultureUsers.objects.get(auth_user_id=maria.pk).active
    form = admin_client.get(url).context["adminform"].form
    assert form["apps"].initial == ["political-culture"]

    # Ticking it again gives back the same row, with the data that points to it.
    admin_client.post(url, change_data("maria", apps=["plants"]))

    assert PlantsUsers.objects.get(pk=in_plants.pk).active
    assert not PoliticalCultureUsers.objects.get(auth_user_id=maria.pk).active


@DATABASES
def test_the_users_list_shows_the_apps_each_person_can_use(
    admin_client: Client,
) -> None:
    maria = get_user_model().objects.create_user(username="maria")
    PlantsUsers.objects.create(auth_user_id=maria.pk)
    PoliticalCultureUsers.objects.create(auth_user_id=maria.pk, active=False)
    CfflchUsers.objects.create(auth_user_id=maria.pk)

    page = admin_client.get(USERS_URL).content.decode()

    assert '<td class="field-app_list">plants, cfflch</td>' in page


@DATABASES
def test_the_user_page_puts_active_next_to_the_apps(admin_client: Client) -> None:
    maria = get_user_model().objects.create_user(username="maria")

    page = admin_client.get(f"{USERS_URL}{maria.pk}/change/")

    sections = {section.name: section.fields for section in page.context["adminform"]}
    assert sections["Access"] == ("is_active", "apps")
    assert "is_active" not in sections["Permissions"]


@DATABASES
def test_unticking_active_in_the_list_keeps_the_persons_apps(
    admin_client: Client,
) -> None:
    maria = get_user_model().objects.create_user(username="maria")
    PlantsUsers.objects.create(auth_user_id=maria.pk)

    response = admin_client.post(
        USERS_URL,
        {
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "1",
            "form-0-id": str(maria.pk),
            "_save": "Save",
        },
    )

    assert response.status_code == 302
    maria.refresh_from_db()
    assert not maria.is_active
    assert PlantsUsers.objects.get(auth_user_id=maria.pk).active


@DATABASES
def test_a_staff_user_who_can_only_view_users_opens_a_user_page(
    client: Client,
) -> None:
    viewer = get_user_model().objects.create_user(username="viewer", is_staff=True)
    viewer.user_permissions.add(
        Permission.objects.get(codename="view_user", content_type__app_label="auth")
    )
    maria = get_user_model().objects.create_user(username="maria")
    client.force_login(viewer)

    response = client.get(f"{USERS_URL}{maria.pk}/change/")

    assert response.status_code == 200

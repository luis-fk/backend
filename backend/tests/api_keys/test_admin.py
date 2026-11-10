import html
import re

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from api_keys.models import ApiKey, hash_key
from cfflch.models import Users as CfflchUsers
from plants.models import Users as PlantsUsers
from tests.api_tokens import api_key_for

DATABASES = pytest.mark.django_db(
    databases=["default", "plants_db", "political_culture_db", "cfflch_db"]
)
LIST_URL = "/admin/api_keys/apikey/"
ADD_URL = f"{LIST_URL}add/"
FULL_KEY = re.compile(r"pk_[A-Za-z0-9_-]{43}")


def person_in(*apps: type[PlantsUsers] | type[CfflchUsers]) -> tuple[int, list[int]]:
    """An auth user named maria in the given apps: her id and her id in each."""
    maria = get_user_model().objects.create_user(username="maria")
    return maria.pk, [users.objects.create(auth_user_id=maria.pk).pk for users in apps]


@DATABASES
def test_the_admin_shows_a_new_key_only_once(admin_client: Client) -> None:
    maria, _ = person_in(PlantsUsers)

    response = admin_client.post(
        ADD_URL, {"name": "Bruno", "person": maria, "apps": ["plants"]}, follow=True
    )

    page = html.unescape(response.content.decode())
    shown = FULL_KEY.findall(page)
    assert len(shown) == 1
    assert "won't be shown again" in page
    # Not through the messages cookie, which is signed but readable.
    assert "messages" not in response.cookies

    row = ApiKey.objects.values().get()
    assert row["key_hash"] == hash_key(shown[0])
    assert shown[0] not in str(row)

    for url in [LIST_URL, f"{LIST_URL}{row['id']}/change/"]:
        assert not FULL_KEY.search(admin_client.get(url).content.decode())


@DATABASES
def test_a_key_for_several_apps_keeps_the_persons_id_in_each(
    admin_client: Client,
) -> None:
    maria, (in_plants, in_cfflch) = person_in(PlantsUsers, CfflchUsers)

    admin_client.post(
        ADD_URL, {"name": "Bruno", "person": maria, "apps": ["plants", "cfflch"]}
    )

    key = ApiKey.objects.get()
    assert key.auth_user_id == maria
    assert key.users == {"plants": in_plants, "cfflch": in_cfflch}


@DATABASES
def test_the_admin_refuses_an_app_the_person_is_not_in(admin_client: Client) -> None:
    maria, _ = person_in(PlantsUsers)

    response = admin_client.post(
        ADD_URL, {"name": "Bruno", "person": maria, "apps": ["plants", "cfflch"]}
    )

    errors = response.context["adminform"].form.errors
    assert errors == {
        "apps": ["maria isn't in cfflch: add them on their user page first."]
    }
    assert not ApiKey.objects.exists()


@DATABASES
def test_the_keys_list_shows_the_person_and_the_apps(admin_client: Client) -> None:
    maria, (in_plants, in_cfflch) = person_in(PlantsUsers, CfflchUsers)
    api_key_for({"plants": in_plants, "cfflch": in_cfflch})
    ApiKey.objects.update(auth_user_id=maria)

    page = admin_client.get(LIST_URL).content.decode()

    assert "maria" in page
    assert "plants, cfflch" in page


@DATABASES
def test_the_admin_changes_only_the_name_and_whether_the_key_is_active(
    admin_client: Client,
) -> None:
    maria, (in_plants,) = person_in(PlantsUsers)
    original = api_key_for({"plants": in_plants})
    key = ApiKey.objects.get()
    key.auth_user_id = maria
    key.save()

    response = admin_client.post(
        f"{LIST_URL}{key.pk}/change/",
        {"name": "Bruno", "person": 99, "apps": ["cfflch"]},
    )

    assert response.status_code == 302
    key.refresh_from_db()
    assert (key.name, key.auth_user_id, key.users, key.active) == (
        "Bruno",
        maria,
        {"plants": in_plants},
        False,
    )
    # Saving doesn't replace the key, so the one in Bruno keeps working.
    assert key.key_hash == hash_key(original)

import html
import re
from unittest.mock import patch

import pytest
from django.test import Client

from api_keys.models import ApiKey, hash_key
from tests.api_tokens import api_key

LIST_URL = "/admin/api_keys/apikey/"
ADD_URL = f"{LIST_URL}add/"
FULL_KEY = re.compile(r"pk_[A-Za-z0-9_-]{43}")


@pytest.mark.django_db
def test_the_admin_shows_a_new_key_only_once(admin_client: Client) -> None:
    with patch("political_culture.models.Users.objects") as users:
        users.filter.return_value.exists.return_value = True
        response = admin_client.post(
            ADD_URL,
            {"name": "Bruno", "app": "political-culture", "user_id": 7},
            follow=True,
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


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("app", "users_model"),
    [
        ("plants", "plants.models.Users"),
        ("political-culture", "political_culture.models.Users"),
        ("cfflch", "cfflch.models.Users"),
    ],
)
def test_the_admin_refuses_a_user_the_app_does_not_have(
    admin_client: Client, app: str, users_model: str
) -> None:
    with patch(f"{users_model}.objects") as users:
        users.filter.return_value.exists.return_value = False
        response = admin_client.post(
            ADD_URL, {"name": "Bruno", "app": app, "user_id": 99}
        )

    users.filter.assert_called_once_with(pk=99)
    errors = response.context["adminform"].form.errors
    assert errors == {"user_id": [f"{app} has no user with id 99."]}
    assert not ApiKey.objects.exists()


@pytest.mark.django_db
def test_the_admin_changes_only_the_name_and_whether_the_key_is_active(
    admin_client: Client,
) -> None:
    original = api_key("plants", 7)
    key = ApiKey.objects.get()

    response = admin_client.post(
        f"{LIST_URL}{key.pk}/change/",
        {"name": "Bruno", "app": "cfflch", "user_id": 8},
    )

    assert response.status_code == 302
    key.refresh_from_db()
    assert (key.name, key.app, key.user_id, key.active) == ("Bruno", "plants", 7, False)
    # Saving doesn't replace the key, so the one in Bruno keeps working.
    assert key.key_hash == hash_key(original)

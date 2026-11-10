import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from political_culture.models import Users

DATABASES = pytest.mark.django_db(databases=["default", "political_culture_db"])
USERS_URL = "/admin/political_culture/users/"


@DATABASES
def test_the_users_list_shows_each_persons_name(admin_client: Client) -> None:
    maria = get_user_model().objects.create_user(username="maria")
    Users.objects.create(auth_user_id=maria.pk)

    page = admin_client.get(USERS_URL).content.decode()

    assert "maria" in page


@DATABASES
# A pasted name can bring spaces around it.
@pytest.mark.parametrize("term", ["mar", " mar "])
def test_the_users_list_finds_a_person_by_name(admin_client: Client, term: str) -> None:
    for name in ["maria", "joana"]:
        person = get_user_model().objects.create_user(username=name)
        Users.objects.create(auth_user_id=person.pk)

    page = admin_client.get(USERS_URL, {"q": term}).content.decode()

    assert "maria" in page
    assert "joana" not in page


@DATABASES
def test_the_users_list_shows_and_filters_who_is_blocked(admin_client: Client) -> None:
    for name, active in [("maria", True), ("joana", False)]:
        person = get_user_model().objects.create_user(username=name)
        Users.objects.create(auth_user_id=person.pk, active=active)

    page = admin_client.get(USERS_URL, {"active__exact": "0"}).content.decode()

    assert "column-active" in page
    assert 'href="?active__exact=0"' in page
    assert "joana" in page
    assert "maria" not in page

import html
import re
from typing import Any

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client

from plants.api.esp32.devices import device_for_key
from plants.models import Esp32Data, Esp32Device, Users
from tests.api_tokens import saved_device

DATABASES = pytest.mark.django_db(databases=["default", "plants_db"])
LIST_URL = "/admin/plants/esp32device/"
ADD_URL = f"{LIST_URL}add/"
FULL_KEY = re.compile(r"dk_[A-Za-z0-9_-]{43}")
NO_LOCATION = "No location: readings come without the weather"


def plants_person(name: str, active: bool = True, **fields: Any) -> Users:
    person = get_user_model().objects.create_user(username=name)
    return Users.objects.create(auth_user_id=person.pk, active=active, **fields)


def new_device(person: Users) -> dict[str, Any]:
    return {
        "nickname": "Manjericão",
        "user": person.pk,
        "dry_value": 4095,
        "wet_value": 0,
        "active": "on",
    }


@DATABASES
def test_a_new_device_shows_its_key_once(admin_client: Client) -> None:
    maria = plants_person("maria", latitude="-25.43", longitude="-49.27")

    response = admin_client.post(ADD_URL, new_device(maria), follow=True)

    shown = FULL_KEY.findall(html.unescape(response.content.decode()))
    assert len(shown) == 1
    device = Esp32Device.objects.get()
    assert device_for_key(shown[0]) == device
    for url in [LIST_URL, f"{LIST_URL}{device.pk}/change/"]:
        assert not FULL_KEY.search(admin_client.get(url).content.decode())


@DATABASES
def test_the_person_is_picked_among_people_who_can_use_plants(
    admin_client: Client,
) -> None:
    plants_person("maria")
    joana = plants_person("joana", active=False)

    page = admin_client.get(ADD_URL).content.decode()
    response = admin_client.post(ADD_URL, new_device(joana))

    assert ">maria</option>" in page
    assert ">joana</option>" not in page
    assert "user" in response.context["adminform"].form.errors
    assert not Esp32Device.objects.exists()


@DATABASES
def test_a_new_key_replaces_the_old_one(admin_client: Client) -> None:
    device, old_key = saved_device()
    Esp32Data.objects.create(
        analog_value=2000, digital_value=1, user=device.user, device=device
    )

    response = admin_client.post(
        LIST_URL, {"action": "new_key", "_selected_action": [device.pk]}
    )

    [new_key] = FULL_KEY.findall(html.unescape(response.content.decode()))
    assert device_for_key(old_key) is None
    assert device_for_key(new_key) == device
    assert device.readings.count() == 1


@DATABASES
def test_a_new_key_is_made_for_one_device_at_a_time(admin_client: Client) -> None:
    first, first_key = saved_device()
    second, _ = saved_device("Samambaia")

    response = admin_client.post(
        LIST_URL,
        {"action": "new_key", "_selected_action": [first.pk, second.pk]},
        follow=True,
    )

    assert "Pick one device to give a new key." in response.content.decode()
    assert device_for_key(first_key) == first


@DATABASES
def test_the_list_warns_about_an_owner_without_a_location(
    admin_client: Client,
) -> None:
    saved_device("Manjericão")
    without, _ = saved_device("Samambaia", latitude=None, longitude=None)

    page = admin_client.get(LIST_URL).content.decode()
    change_page = admin_client.get(f"{LIST_URL}{without.pk}/change/").content.decode()

    assert page.count(NO_LOCATION) == 1
    assert NO_LOCATION in change_page


@DATABASES
def test_a_staff_user_who_can_only_view_devices_cant_make_a_key(
    client: Client,
) -> None:
    device, key = saved_device()
    viewer = get_user_model().objects.create_user(username="viewer", is_staff=True)
    viewer.user_permissions.add(
        Permission.objects.get(
            codename="view_esp32device", content_type__app_label="plants"
        )
    )
    client.force_login(viewer)

    page = client.get(LIST_URL).content.decode()
    response = client.post(
        LIST_URL, {"action": "new_key", "_selected_action": [device.pk]}, follow=True
    )

    assert 'value="new_key"' not in page
    assert not FULL_KEY.search(html.unescape(response.content.decode()))
    assert device_for_key(key) == device

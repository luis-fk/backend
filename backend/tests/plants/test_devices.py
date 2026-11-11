import hashlib

import pytest
from django.db import IntegrityError

from plants.models import Esp32Data, Esp32Device, Users

DATABASES = pytest.mark.django_db(databases=["default", "plants_db"])


def device(owner: Users, nickname: str) -> Esp32Device:
    plant = Esp32Device(user=owner, nickname=nickname)
    plant.generate_key()
    plant.save()
    return plant


def test_a_new_key_is_kept_only_as_its_prefix_and_hash() -> None:
    plant = Esp32Device(nickname="Manjericão")

    key = plant.generate_key()

    assert key.startswith("dk_") and len(key) > 40
    assert plant.prefix == key[:11]
    assert plant.key_hash == hashlib.sha256(key.encode()).hexdigest()


@pytest.mark.parametrize(
    ("raw", "percent"), [(4095, 0), (0, 100), (2048, 50), (5000, 0), (-10, 100)]
)
def test_the_soil_percentage_follows_the_default_calibration(
    raw: int, percent: int
) -> None:
    assert Esp32Device().soil_percent(raw) == percent


def test_swapping_the_calibration_inverts_the_percentage() -> None:
    assert Esp32Device(dry_value=1000, wet_value=3000).soil_percent(2500) == 75


def test_an_equal_calibration_gives_no_percentage() -> None:
    assert Esp32Device(dry_value=2000, wet_value=2000).soil_percent(1500) is None


@DATABASES
def test_a_nickname_is_unique_per_person_only() -> None:
    ana = Users.objects.create(auth_user_id=1)
    bia = Users.objects.create(auth_user_id=2)
    device(ana, "Manjericão")
    device(bia, "Manjericão")

    with pytest.raises(IntegrityError):
        device(ana, "Manjericão")


@DATABASES
def test_deleting_a_device_deletes_its_readings() -> None:
    ana = Users.objects.create(auth_user_id=1)
    plant = device(ana, "Manjericão")
    Esp32Data.objects.create(analog_value=2000, digital_value=1, user=ana, device=plant)

    plant.delete()

    assert not Esp32Data.objects.exists()

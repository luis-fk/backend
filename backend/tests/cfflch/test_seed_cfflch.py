from datetime import datetime
from io import StringIO
from zoneinfo import ZoneInfo

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client

from cfflch.api.admission_status.utils import normalize_text
from cfflch.models import AdmissionPDF, AdmissionResult, ClassRoom, Users
from tests.api_tokens import bearer, login_token, user_token

DATABASES = pytest.mark.django_db(databases=["default", "cfflch_db"])
# Each seeded student's class and whether they were approved.
STUDENTS = {
    "Aurora Menezes Lago": ("Turma A", True),
    "Benício Prates Rocha": ("Turma A", False),
    "Celina Duarte Vaz": ("Turma A", True),
    "Davi Antunes Leal": ("Turma B", True),
    "Elisa Moraes Brito": ("Turma B", False),
    "Gael Fontes Ribeiro": ("Turma B", True),
}
LOCAL = {"ENGINE": "django.db.backends.postgresql", "HOST": "localhost"}
REMOTE = {
    "ENGINE": "django.db.backends.postgresql",
    "HOST": "x.proxy.rlwy.net",
    "PASSWORD": "secret-password",
}


def seed() -> None:
    call_command("seed_cfflch", stdout=StringIO())


def this_year() -> int:
    """The year the site opens on, in Brazil."""
    return datetime.now(ZoneInfo("America/Sao_Paulo")).year


def demo_token(client: Client) -> str:
    """A user token for demo, signed after looking demo up by name, as the login
    does."""
    response = client.get(
        "/api/cfflch/users/demo", headers=bearer(login_token("cfflch"))
    )
    return user_token("cfflch", str(response.json()["id"]))


@DATABASES
def test_the_seed_gives_demo_two_classes_and_six_students_of_this_year() -> None:
    seed()

    demo = get_user_model().objects.get(username="demo")
    assert demo.is_active
    assert not demo.has_usable_password()
    assert Users.objects.get(auth_user_id=demo.pk).active
    assert sorted(ClassRoom.objects.values_list("name", "name_normalized")) == [
        ("Turma A", "turma a"),
        ("Turma B", "turma b"),
    ]
    saved = AdmissionResult.objects.values_list(
        "student_name",
        "student_name_normalized",
        "year",
        "class_room__name",
        "approved",
    )
    assert sorted(saved) == sorted(
        (name, normalize_text(name), this_year(), class_name, approved)
        for name, (class_name, approved) in STUDENTS.items()
    )
    assert not AdmissionPDF.objects.exists()


@DATABASES
@pytest.mark.access_check
def test_demo_logs_in_and_the_site_lists_the_students_of_this_year(
    client: Client,
) -> None:
    seed()

    response = client.get(
        "/api/cfflch/admission-results/",
        {"year": this_year()},
        headers=bearer(demo_token(client)),
    )

    assert response.status_code == 200
    assert sorted(result["student_name"] for result in response.json()) == sorted(
        STUDENTS
    )


@DATABASES
def test_a_second_run_restores_the_seed_and_leaves_other_students_alone() -> None:
    seed()
    benicio = AdmissionResult.objects.get(student_name="Benício Prates Rocha")
    class_a = benicio.class_room_id
    benicio.approved = True
    benicio.class_room = None
    benicio.save()
    fulano = AdmissionResult.objects.create(
        student_name="Fulano de Tal",
        student_name_normalized="fulano de tal",
        year=this_year(),
        approved=True,
        class_room_id=class_a,
    )

    seed()

    assert ClassRoom.objects.count() == 2
    assert AdmissionResult.objects.exclude(pk=fulano.pk).count() == 6
    benicio.refresh_from_db()
    assert (benicio.approved, benicio.class_room_id) == (False, class_a)
    fulano.refresh_from_db()
    assert (fulano.approved, fulano.class_room_id) == (True, class_a)


@DATABASES
def test_a_second_run_lets_a_blocked_demo_in_again() -> None:
    seed()
    get_user_model().objects.filter(username="demo").update(is_active=False)
    Users.objects.update(active=False)

    seed()

    demo = get_user_model().objects.get(username="demo")
    assert demo.is_active
    assert Users.objects.get(auth_user_id=demo.pk).active


@DATABASES
def test_a_remote_database_stops_the_seed_before_it_writes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "DATABASES", {"default": LOCAL, "cfflch_db": REMOTE})

    with pytest.raises(CommandError) as error:
        seed()

    assert "cfflch_db (x.proxy.rlwy.net)" in str(error.value)
    assert "secret-password" not in str(error.value)
    assert not get_user_model().objects.filter(username="demo").exists()
    assert not Users.objects.exists()
    assert not ClassRoom.objects.exists()
    assert not AdmissionResult.objects.exists()

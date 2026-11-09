from typing import Any
from unittest.mock import ANY

import pytest
from django.test import Client

from cfflch.api.admission_status.utils import normalize_text
from cfflch.models import AdmissionPDF, AdmissionResult, ClassRoom
from tests.api_tokens import bearer, user_token

DATABASES = pytest.mark.django_db(databases=["default", "cfflch_db"])
HEADERS = bearer(user_token("cfflch"))


def list_results(client: Client, **params: Any) -> tuple[int, Any]:
    response = client.get("/api/cfflch/admission-results/", params, headers=HEADERS)
    return response.status_code, response.json()


def update_result(client: Client, pk: int, body: dict[str, Any]) -> tuple[int, Any]:
    response = client.patch(
        f"/api/cfflch/admission-results/{pk}/",
        body,
        content_type="application/json",
        headers=HEADERS,
    )
    return response.status_code, response.json()


def student(name: str, year: int = 2025, **fields: Any) -> AdmissionResult:
    return AdmissionResult.objects.create(
        student_name=name,
        student_name_normalized=normalize_text(name),
        year=year,
        **fields,
    )


def class_room(name: str) -> ClassRoom:
    return ClassRoom.objects.create(name=name, name_normalized=normalize_text(name))


@DATABASES
def test_the_results_of_a_year_come_with_their_lists(client: Client) -> None:
    class_a = class_room("3A")
    fulano = student("Fulano de Tal", class_room=class_a, approved=True)
    AdmissionPDF.objects.create(
        result=fulano, url="https://exemplo.br/aprovados.pdf", search_title="Aprovados"
    )
    student("Fulano de Tal", year=2024)

    status, results = list_results(client, year=2025)

    assert status == 200
    assert results == [
        {
            "id": fulano.id,
            "student_name": "Fulano de Tal",
            "year": 2025,
            "approved": True,
            "class_room_id": class_a.id,
            "created_at": ANY,
            "pdf_urls": [
                {"url": "https://exemplo.br/aprovados.pdf", "search_title": "Aprovados"}
            ],
        }
    ]


@DATABASES
def test_the_results_can_be_narrowed_to_a_class_room(client: Client) -> None:
    class_b = class_room("3B")
    student("Fulano de Tal", class_room=class_room("3A"))
    student("Beltrana Conceição", class_room=class_b)
    student("Sicrano Araújo")

    _, results = list_results(client, year=2025, class_room_id=class_b.id)

    assert [result["student_name"] for result in results] == ["Beltrana Conceição"]


@pytest.mark.parametrize(
    ("params", "error"),
    [
        ({}, "year query parameter is required"),
        ({"year": "2025a"}, "year must be an integer"),
        ({"year": 2025, "class_room_id": "3A"}, "class_room_id must be an integer"),
    ],
    ids=["no year", "year not a number", "class room not a number"],
)
def test_a_list_with_bad_filters_gets_400(
    client: Client, params: dict[str, Any], error: str
) -> None:
    assert list_results(client, **params) == (400, {"error": error})


@DATABASES
def test_approving_a_result_keeps_its_class_room(client: Client) -> None:
    class_a = class_room("3A")
    fulano = student("Fulano de Tal", class_room=class_a)

    status, _ = update_result(client, fulano.id, {"approved": True})

    assert status == 200
    fulano.refresh_from_db()
    assert fulano.approved
    assert fulano.class_room_id == class_a.id


@DATABASES
def test_a_result_can_move_to_a_class_room_and_out_of_it(client: Client) -> None:
    fulano = student("Fulano de Tal")
    class_a = class_room("3A")

    _, moved = update_result(client, fulano.id, {"class_room_id": class_a.id})
    _, removed = update_result(client, fulano.id, {"class_room_id": None})

    assert moved["class_room_id"] == class_a.id
    assert removed["class_room_id"] is None
    fulano.refresh_from_db()
    assert fulano.class_room is None


@DATABASES
def test_an_unknown_class_room_gets_404_and_changes_nothing(client: Client) -> None:
    fulano = student("Fulano de Tal")

    answer = update_result(client, fulano.id, {"approved": True, "class_room_id": 999})

    assert answer == (404, {"error": "ClassRoom not found"})
    fulano.refresh_from_db()
    assert not fulano.approved


@DATABASES
def test_an_invalid_change_gets_400(client: Client) -> None:
    fulano = student("Fulano de Tal")

    status, errors = update_result(client, fulano.id, {"approved": "talvez"})

    assert status == 400
    assert "approved" in errors


@DATABASES
def test_deleting_a_result_deletes_its_lists(client: Client) -> None:
    fulano = student("Fulano de Tal")
    AdmissionPDF.objects.create(result=fulano, url="https://exemplo.br/lista.pdf")
    beltrana = student("Beltrana Conceição")

    response = client.delete(
        f"/api/cfflch/admission-results/{fulano.id}/", headers=HEADERS
    )

    assert response.status_code == 204
    assert list(AdmissionResult.objects.all()) == [beltrana]
    assert not AdmissionPDF.objects.exists()

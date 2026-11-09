import pytest
from django.test import Client

from cfflch.models import ClassRoom
from tests.api_tokens import bearer, user_token


@pytest.mark.django_db(databases=["default", "cfflch_db"])
def test_the_class_rooms_are_listed_by_name(client: Client) -> None:
    class_b = ClassRoom.objects.create(name="3B", name_normalized="3b")
    class_a = ClassRoom.objects.create(name="3A", name_normalized="3a")

    response = client.get(
        "/api/cfflch/class-rooms/", headers=bearer(user_token("cfflch"))
    )

    assert response.json() == [
        {"id": class_a.id, "name": "3A"},
        {"id": class_b.id, "name": "3B"},
    ]

import pytest
from django.test import Client

from plants.models import ChatHistory, Users
from tests.api_tokens import bearer, user_token


@pytest.mark.django_db(databases=["default", "plants_db"])
def test_the_chat_history_is_the_users_messages_in_order(client: Client) -> None:
    fulano = Users.objects.create(auth_user_id=1)
    beltrana = Users.objects.create(auth_user_id=2)
    ChatHistory.objects.create(user=fulano, role="human", message="Quando rego?")
    ChatHistory.objects.create(user=beltrana, role="human", message="E o cacto?")
    ChatHistory.objects.create(user=fulano, role="ai", message="Arr, às segundas!")

    response = client.get(
        f"/api/chat-history/{fulano.id}/",
        headers=bearer(user_token("plants", str(fulano.id))),
    )

    assert response.json() == [
        {"role": "human", "message": "Quando rego?"},
        {"role": "ai", "message": "Arr, às segundas!"},
    ]

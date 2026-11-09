import pytest
from django.test import Client

from political_culture.models import ChatHistory, Users
from tests.api_tokens import bearer, user_token


@pytest.mark.django_db(databases=["default", "political_culture_db"])
def test_the_chat_history_is_the_users_messages_in_order(client: Client) -> None:
    fulano = Users.objects.create(auth_user_id=1)
    beltrana = Users.objects.create(auth_user_id=2)
    ChatHistory.objects.create(user=fulano, role="human", message="Quem foi Gramsci?")
    ChatHistory.objects.create(user=beltrana, role="human", message="E Hobbes?")
    ChatHistory.objects.create(user=fulano, role="ai", message="Um filósofo italiano.")

    response = client.get(
        f"/api/political-culture/chat-history/{fulano.id}",
        headers=bearer(user_token("political-culture", str(fulano.id))),
    )

    assert response.json() == [
        {"role": "human", "message": "Quem foi Gramsci?"},
        {"role": "ai", "message": "Um filósofo italiano."},
    ]

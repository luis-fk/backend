import threading
from collections.abc import Iterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from django.test import Client

from political_culture.api.chatbot import chatbot
from political_culture.api.chatbot.chatbot import LLM
from political_culture.api.chatbot.routes import ChatBotApi
from political_culture.models import ChatHistory, UserMemory, Users
from tests.api_tokens import bearer, user_token

# transaction=True: the processing starts by closing the thread's old connections,
# which a test wrapped in a transaction would not survive.
DATABASES = pytest.mark.django_db(
    databases=["default", "political_culture_db"], transaction=True
)


def send_message(client: Client, body: dict[str, Any]) -> tuple[int, Any]:
    response = client.post(
        "/api/political-culture/chatbot/message",
        body,
        content_type="application/json",
        headers=bearer(user_token("political-culture", "7")),
    )
    return response.status_code, response.json()


def test_the_chatbot_reads_the_text_without_its_html(client: Client) -> None:
    with patch.object(ChatBotApi, "llm") as llm:
        answer = send_message(
            client, {"user_id": 7, "text": "<p>O <b>Estado</b> e a revolução</p>"}
        )

    assert answer == (200, {"user_id": 7, "response": "accepted"})
    llm.process_text.assert_called_once_with(
        text="O Estado e a revolução", user_id=7, language="pt-BR"
    )


def test_the_page_language_goes_with_the_message(client: Client) -> None:
    with patch.object(ChatBotApi, "llm") as llm:
        answer = send_message(client, {"user_id": 7, "text": "/help", "language": "en"})

    assert answer == (200, {"user_id": 7, "response": "accepted"})
    llm.process_text.assert_called_once_with(text="/help", user_id=7, language="en")


def test_a_language_the_site_lacks_gets_400(client: Client) -> None:
    with patch.object(ChatBotApi, "llm") as llm:
        answer = send_message(client, {"user_id": 7, "text": "/help", "language": "fr"})

    assert answer == (400, {"error": "Invalid request data"})
    llm.process_text.assert_not_called()


def test_a_message_without_text_gets_400(client: Client) -> None:
    with patch.object(ChatBotApi, "llm") as llm:
        answer = send_message(client, {"user_id": 7})

    assert answer == (400, {"error": "Invalid request data"})
    llm.process_text.assert_not_called()


def test_the_text_is_processed_after_the_request_in_another_thread() -> None:
    can_finish = threading.Event()
    finished = threading.Event()

    def process(text: str, user_id: int, language: str) -> None:
        can_finish.wait(timeout=5)
        finished.set()

    llm = LLM()
    with patch.object(llm, "_background_process", side_effect=process) as background:
        llm.process_text("Quem foi Gramsci?", 7, "pt-BR")
        assert not finished.is_set()
        can_finish.set()
        assert finished.wait(timeout=5)

    background.assert_called_once_with("Quem foi Gramsci?", 7, "pt-BR")


@pytest.fixture
def channel_layer() -> Iterator[MagicMock]:
    """A channel layer that records what the processing sends."""
    with patch.object(chatbot, "get_channel_layer") as get_channel_layer:
        get_channel_layer.return_value.group_send = AsyncMock()
        yield get_channel_layer.return_value


@DATABASES
def test_after_processing_the_answer_goes_to_the_users_socket(
    channel_layer: MagicMock,
) -> None:
    user = Users.objects.create(auth_user_id=1)
    UserMemory.objects.create(user=user, memory="Gosta de história.")

    def answer(**_graph_options: Any) -> None:
        ChatHistory.objects.create(user=user, role="ai", message="Um filósofo.")

    llm = LLM()
    with patch.object(llm, "graph") as graph:
        graph.invoke.side_effect = answer
        llm._background_process("Quem foi Gramsci?", user.id, "pt-BR")

    graph.invoke.assert_called_once_with(
        input={
            "input": "Quem foi Gramsci?",
            "memory": "Gosta de história.",
            "user_id": user.id,
        },
        config={"recursion_limit": 50},
    )
    channel_layer.group_send.assert_awaited_once_with(
        f"chat_{user.id}",
        {"type": "chat.message", "message": {"role": "ai", "message": "Um filósofo."}},
    )


@DATABASES
def test_a_failed_processing_is_logged_and_reported_to_the_socket(
    channel_layer: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    user = Users.objects.create(auth_user_id=1)

    llm = LLM()
    with patch.object(llm, "graph") as graph:
        graph.invoke.side_effect = RuntimeError("OpenAI is down")
        llm._background_process("Quem foi Gramsci?", user.id, "pt-BR")

    assert f"Error in background processing for user {user.id}" in caplog.text
    assert "OpenAI is down" in caplog.text
    channel_layer.group_send.assert_awaited_once_with(
        f"chat_{user.id}", {"type": "chat.message", "message": {"failed": True}}
    )


@DATABASES
@pytest.mark.parametrize(
    ("language", "opening", "summary"),
    [("pt-BR", "Posso ajudar", "resumo"), ("en", "I can help", "summary")],
)
def test_help_tells_what_the_bot_does_without_the_model_and_keeps_it_in_the_history(
    channel_layer: MagicMock, language: str, opening: str, summary: str
) -> None:
    user = Users.objects.create(auth_user_id=1)

    llm = LLM()
    with patch.object(llm, "graph") as graph:
        llm._background_process(" /Help ", user.id, language)

    graph.invoke.assert_not_called()
    saved = list(
        ChatHistory.objects.filter(user=user)
        .order_by("id")
        .values_list("role", "message")
    )
    assert saved[0] == ("human", "/Help")
    role, help_text = saved[1]
    assert role == "ai"
    assert help_text.startswith(opening)
    assert summary in help_text
    channel_layer.group_send.assert_awaited_once_with(
        f"chat_{user.id}",
        {"type": "chat.message", "message": {"role": "ai", "message": help_text}},
    )


@pytest.mark.parametrize(
    ("language", "opening", "ending"),
    [
        ("pt-BR", "Posso ajudar", "Você pode usar o comando /help quando precisar."),
        ("en", "I can help", "You can use the /help command whenever you need it."),
    ],
)
def test_an_empty_chat_opens_with_the_help_and_a_reminder_of_the_command(
    client: Client, language: str, opening: str, ending: str
) -> None:
    response = client.get(
        "/api/political-culture/chatbot/help",
        {"language": language},
        headers=bearer(user_token("political-culture", "7")),
    )

    assert response.status_code == 200
    message = response.json()["message"]
    assert message.startswith(opening)
    assert message.endswith(ending)


def test_the_first_message_is_in_portuguese_without_a_language(client: Client) -> None:
    response = client.get(
        "/api/political-culture/chatbot/help",
        headers=bearer(user_token("political-culture", "7")),
    )

    assert response.status_code == 200
    assert response.json()["message"].startswith("Posso ajudar")


def test_the_first_message_in_a_language_the_site_lacks_gets_400(
    client: Client,
) -> None:
    response = client.get(
        "/api/political-culture/chatbot/help",
        {"language": "fr"},
        headers=bearer(user_token("political-culture", "7")),
    )

    assert response.status_code == 400

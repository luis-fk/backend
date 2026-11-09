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
    llm.process_text.assert_called_once_with(text="O Estado e a revolução", user_id=7)


def test_a_message_without_text_gets_400(client: Client) -> None:
    with patch.object(ChatBotApi, "llm") as llm:
        answer = send_message(client, {"user_id": 7})

    assert answer == (400, {"error": "Invalid request data"})
    llm.process_text.assert_not_called()


def test_the_text_is_processed_after_the_request_in_another_thread() -> None:
    can_finish = threading.Event()
    finished = threading.Event()

    def process(text: str, user_id: int) -> None:
        can_finish.wait(timeout=5)
        finished.set()

    llm = LLM()
    with patch.object(llm, "_background_process", side_effect=process) as background:
        llm.process_text("Quem foi Gramsci?", 7)
        assert not finished.is_set()
        can_finish.set()
        assert finished.wait(timeout=5)

    background.assert_called_once_with("Quem foi Gramsci?", 7)


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
        llm._background_process("Quem foi Gramsci?", user.id)

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
@pytest.mark.usefixtures("channel_layer")
def test_a_failed_processing_is_logged_instead_of_raised(
    caplog: pytest.LogCaptureFixture,
) -> None:
    user = Users.objects.create(auth_user_id=1)

    llm = LLM()
    with patch.object(llm, "graph") as graph:
        graph.invoke.side_effect = RuntimeError("OpenAI is down")
        llm._background_process("Quem foi Gramsci?", user.id)

    assert f"Error in background processing for user {user.id}" in caplog.text
    assert "OpenAI is down" in caplog.text

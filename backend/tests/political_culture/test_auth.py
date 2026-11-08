from collections.abc import Callable
from unittest.mock import ANY, patch

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import HttpResponseBase
from django.test import Client

from political_culture.api.chatbot.routes import ChatBotApi
from political_culture.models import ChatHistory
from tests.api_tokens import bearer, login_token, make_token, user_token

APP = "political-culture"

Send = Callable[[Client, int, dict[str, str]], HttpResponseBase]


def get_history(
    client: Client, user_id: int, headers: dict[str, str]
) -> HttpResponseBase:
    return client.get(f"/api/political-culture/chat-history/{user_id}", headers=headers)


def send_message(
    client: Client, user_id: int, headers: dict[str, str]
) -> HttpResponseBase:
    return client.post(
        "/api/political-culture/chatbot/message",
        {"user_id": user_id, "text": "Olá"},
        content_type="application/json",
        headers=headers,
    )


def count_words(
    client: Client, user_id: int, headers: dict[str, str]
) -> HttpResponseBase:
    pdf = SimpleUploadedFile("texto.pdf", b"%PDF-1.4", content_type="application/pdf")
    return client.post(
        "/api/political-culture/word-counter",
        {"user_id": user_id, "content": pdf},
        headers=headers,
    )


def find_user(client: Client, headers: dict[str, str]) -> HttpResponseBase:
    return client.get("/api/political-culture/users/ana", headers=headers)


@pytest.mark.parametrize("send", [get_history, send_message, count_words])
def test_requests_without_a_token_get_401(client: Client, send: Send) -> None:
    assert send(client, 7, {}).status_code == 401


@pytest.mark.parametrize("send", [get_history, send_message, count_words])
def test_tokens_for_another_app_get_401(client: Client, send: Send) -> None:
    headers = bearer(user_token("plants", "7"))

    assert send(client, 7, headers).status_code == 401


@pytest.mark.parametrize("send", [get_history, send_message, count_words])
def test_tokens_for_another_user_get_403(client: Client, send: Send) -> None:
    headers = bearer(user_token(APP, "7"))

    assert send(client, 8, headers).status_code == 403


def test_users_read_their_own_chat_history(client: Client) -> None:
    with patch.object(ChatHistory.objects, "filter") as history:
        response = get_history(client, 7, bearer(user_token(APP, "7")))

    assert response.status_code == 200
    history.assert_called_once_with(user_id="7")


def test_users_send_their_own_messages(client: Client) -> None:
    with patch.object(ChatBotApi, "llm") as llm:
        response = send_message(client, 7, bearer(user_token(APP, "7")))

    assert response.status_code == 200
    llm.process_text.assert_called_once_with(text="Olá", user_id=7)


def test_users_count_words_in_their_own_texts(client: Client) -> None:
    with (
        patch("political_culture.api.word_counter.routes.add_text") as add_text,
        patch("political_culture.api.word_counter.routes.add_text_word_count"),
    ):
        response = count_words(client, 7, bearer(user_token(APP, "7")))

    assert response.status_code == 200
    add_text.assert_called_once_with(ANY, 7, user_submitted_text=False)


def test_the_login_lookup_without_a_token_gets_401(client: Client) -> None:
    assert find_user(client, {}).status_code == 401


@pytest.mark.parametrize(
    ("app", "purpose"),
    [(APP, "user"), ("plants", "login")],
    ids=["user token", "another app's login token"],
)
def test_the_login_lookup_with_another_token_gets_401(
    client: Client, app: str, purpose: str
) -> None:
    headers = bearer(make_token(sub="7", app=app, purpose=purpose))

    assert find_user(client, headers).status_code == 401


def test_the_login_lookup_runs_with_a_login_token(client: Client) -> None:
    AuthUser = get_user_model()
    with patch.object(AuthUser.objects, "using") as using:
        using.return_value.get.side_effect = AuthUser.DoesNotExist
        response = find_user(client, bearer(login_token(APP)))

    assert response.status_code == 404
    using.return_value.get.assert_called_once_with(username="ana")

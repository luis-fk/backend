import pytest

from political_culture.api.chatbot.utils import (
    clean_html,
    singleton,
    wrap_up_get_response,
)
from political_culture.models import ChatHistory, Users

DATABASES = pytest.mark.django_db(databases=["default", "political_culture_db"])


def test_a_singleton_class_is_built_once() -> None:
    builds: list[str] = []

    @singleton
    class Graph:
        def __init__(self) -> None:
            builds.append("built")

    assert Graph() is Graph()
    assert builds == ["built"]


@pytest.mark.parametrize(
    ("html", "text"),
    [
        ("<p>O <b>Estado</b> e a revolução</p>", "O Estado e a revolução"),
        ('<a href="https://exemplo.br">Manifesto</a>', "Manifesto"),
        ("Sem marcação.", "Sem marcação."),
    ],
)
def test_clean_html_keeps_only_the_text(html: str, text: str) -> None:
    assert clean_html(html) == text


@DATABASES
def test_the_socket_gets_the_users_latest_answer() -> None:
    fulano = Users.objects.create(auth_user_id=1)
    beltrana = Users.objects.create(auth_user_id=2)
    ChatHistory.objects.create(user=fulano, role="ai", message="Primeira resposta")
    ChatHistory.objects.create(user=fulano, role="ai", message="Última resposta")
    ChatHistory.objects.create(user=fulano, role="human", message="Obrigado!")
    ChatHistory.objects.create(user=beltrana, role="ai", message="Outra conversa")

    assert wrap_up_get_response(fulano.id) == {
        "role": "ai",
        "message": "Última resposta",
    }


@DATABASES
def test_without_answers_the_socket_gets_an_empty_message() -> None:
    user = Users.objects.create(auth_user_id=1)

    assert wrap_up_get_response(user.id) == {}

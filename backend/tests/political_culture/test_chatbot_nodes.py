from typing import Any, cast
from unittest.mock import ANY, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from political_culture.api.chatbot import agents, nodes, utils
from political_culture.api.chatbot.schemas import ChatInfo, Routes, Routing, SquadState
from political_culture.api.word_counter.schemas import (
    TitleAndAuthorSchema,
    WordCount,
    WordFrequencySquema,
)
from political_culture.models import ChatHistory, Texts, UserMemory, Users

DATABASES = pytest.mark.django_db(databases=["default", "political_culture_db"])


def state(**values: Any) -> SquadState:
    return cast(SquadState, values)


@pytest.mark.parametrize("route", [Routes.CHAT, Routes.ANALYSIS])
def test_the_graph_follows_the_route_the_model_picked(route: Routes) -> None:
    with patch.object(
        agents, "call_router_agent", return_value=Routing(route=route)
    ) as call_router:
        routed = nodes.router(state(input="Quem foi Gramsci?"))

    assert nodes.route_picker(routed) == route.value
    call_router.assert_called_once_with(message="Quem foi Gramsci?")


def test_an_unknown_route_stops_the_graph() -> None:
    with pytest.raises(ValueError, match="word_analysis"):
        nodes.route_picker(state(route="word_analysis"))


@DATABASES
def test_a_pasted_text_is_saved_as_the_users_own_with_its_word_count() -> None:
    user = Users.objects.create(auth_user_id=1)
    info = TitleAndAuthorSchema(
        reasoning="O texto não tem título.",
        title=None,
        author="Fulano de Tal",
        content_description="Um manifesto sobre o Estado.",
    )
    picked = WordFrequencySquema(
        reasoning="Palavras do tema.", words_list=[WordCount(word="estado", count=2)]
    )

    with (
        patch.object(utils, "extract_text_info", return_value=info) as extract,
        patch.object(utils, "word_picker", return_value=picked) as word_picker,
    ):
        extracted = nodes.text_info_extraction(
            state(input="O Estado e o estado das coisas.", user_id=user.id)
        )

    text = Texts.objects.get()
    assert (text.user_id, text.user_submitted_text) == (user.id, True)
    assert (text.title, text.author) == (None, "Fulano de Tal")
    assert text.content_description == "Um manifesto sobre o Estado."
    assert text.analysis.word_frequencies == {"estado": 2}
    assert (extracted["title"], extracted["author"]) == ("unknown", "Fulano de Tal")
    assert extracted["word_count"] == text.analysis.word_frequencies
    extract.assert_called_once_with("O Estado e o estado das coisas.")
    word_picker.assert_called_once_with(ANY, "Um manifesto sobre o Estado.")


def test_the_three_analyses_are_merged_in_order() -> None:
    with patch.object(
        agents, "call_text_concatenation_agent", return_value="Análise completa"
    ) as merge:
        merged = nodes.text_concatenation(
            state(
                word_analysis_response="Palavras",
                text_analysis_response="Texto",
                ideology_analysis_response="Ideologia",
            )
        )

    merge.assert_called_once_with("Palavras\n\nTexto\n\nIdeologia")
    assert merged["response"] == "Análise completa"


@DATABASES
def test_wrap_up_saves_the_exchange_without_html_and_the_new_memory() -> None:
    user = Users.objects.create(auth_user_id=1)
    UserMemory.objects.create(user=user, memory="Gosta de história.")
    ChatHistory.objects.create(user=user, role="human", message="Oi")
    ChatHistory.objects.create(user=user, role="ai", message="Olá!")
    new_memory = ChatInfo(info="Gosta de história e de Gramsci.")

    with patch.object(
        agents, "call_user_info_agent", return_value=new_memory
    ) as memory:
        nodes.wrap_up(
            state(
                input="Quem foi Gramsci?",
                user_id=user.id,
                memory="Gosta de história.",
                response="<p>Um <b>filósofo</b> italiano.</p>",
            )
        )

    message, history, old_memory = memory.call_args.args
    assert (message, old_memory) == ("Quem foi Gramsci?", "Gosta de história.")
    assert [(type(entry), entry.content) for entry in history] == [
        (HumanMessage, "Oi"),
        (AIMessage, "Olá!"),
    ]
    saved = ChatHistory.objects.filter(user=user).order_by("id")
    assert list(saved.values_list("role", "message")) == [
        ("human", "Oi"),
        ("ai", "Olá!"),
        ("human", "Quem foi Gramsci?"),
        ("ai", "Um filósofo italiano."),
    ]
    assert UserMemory.objects.get(user=user).memory == "Gosta de história e de Gramsci."

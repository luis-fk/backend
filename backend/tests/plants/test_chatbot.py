from collections.abc import Iterator
from typing import Any, NamedTuple, cast
from unittest.mock import MagicMock, patch

import pytest
from django.test import Client
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.messages.tool import tool_call

from plants.api.chatbot import nodes, tools
from plants.api.chatbot.chatbot import LLM
from plants.api.chatbot.routes import ChatBotApi
from plants.api.chatbot.schemas import ChatInfo, LLMAnswerSchema, Routing, SquadState
from plants.models import ChatHistory, UserMemory, Users
from tests.api_tokens import bearer, user_token

DATABASES = pytest.mark.django_db(databases=["default", "plants_db"])


class Agents(NamedTuple):
    router: MagicMock
    chatbot: MagicMock
    web_search: MagicMock
    web_answer: MagicMock
    memory: MagicMock


@pytest.fixture
def agents() -> Iterator[Agents]:
    """The models behind the nodes; the router sends every question to the chatbot."""
    with (
        patch.object(nodes, "call_router_agent") as router,
        patch.object(nodes, "call_chatbot_agent") as chatbot,
        patch.object(nodes, "call_tools_agent") as web_search,
        patch.object(nodes, "call_tool_response_agent") as web_answer,
        patch.object(nodes, "call_user_info_agent") as memory,
    ):
        router.return_value = Routing(route="continue")
        memory.return_value = ChatInfo(info="Mora em Curitiba e tem uma samambaia.")
        yield Agents(router, chatbot, web_search, web_answer, memory)


def saved_messages(user: Users) -> list[tuple[str, str]]:
    return list(
        ChatHistory.objects.filter(user=user)
        .order_by("id")
        .values_list("role", "message")
    )


def ask(user: Users, message: str) -> dict[str, str]:
    """Sends message through the real graph, as the route does; returns the answer."""
    llm = LLM()
    llm.setup()
    answer = llm.process_message(message, user.id)
    assert answer is not None
    return dict(answer.data)


@DATABASES
def test_a_question_is_answered_with_the_earlier_messages_and_saved(
    agents: Agents,
) -> None:
    user = Users.objects.create(auth_user_id=1)
    UserMemory.objects.create(user=user, memory="Mora em Curitiba.")
    ChatHistory.objects.create(user=user, role="human", message="Oi!")
    ChatHistory.objects.create(user=user, role="ai", message="Ahoy, marujo!")
    agents.chatbot.return_value = LLMAnswerSchema(
        reasoning="Samambaias gostam de umidade.", message="Arr, duas vezes por semana!"
    )

    answer = ask(user, "Quando rego a samambaia?")

    assert answer == {"role": "ai", "message": "Arr, duas vezes por semana!"}
    messages = agents.chatbot.call_args.kwargs["messages"]
    assert [(type(message), message.content) for message in messages] == [
        (HumanMessage, "Oi!"),
        (AIMessage, "Ahoy, marujo!"),
        (HumanMessage, "Quando rego a samambaia?"),
    ]
    assert agents.chatbot.call_args.kwargs["memory"] == "Mora em Curitiba."
    assert saved_messages(user) == [
        ("human", "Oi!"),
        ("ai", "Ahoy, marujo!"),
        ("human", "Quando rego a samambaia?"),
        ("ai", "Arr, duas vezes por semana!"),
    ]
    assert UserMemory.objects.get(user=user).memory == (
        "Mora em Curitiba e tem uma samambaia."
    )


@DATABASES
def test_a_question_that_needs_the_web_is_answered_from_the_search(
    agents: Agents,
) -> None:
    user = Users.objects.create(auth_user_id=1)
    agents.router.return_value = Routing(route="tools_agent")
    agents.web_search.return_value = AIMessage(
        content="",
        tool_calls=[
            tool_call(
                name="web_search",
                args={"web_search_input": "previsão de chuva em Curitiba"},
                id="call-1",
            )
        ],
    )
    agents.web_answer.return_value = AIMessage(content="Vai chover, não precisa regar.")

    with patch.object(tools, "TavilySearchResults") as tavily:
        tavily.return_value.invoke.return_value = [{"content": "Chuva amanhã"}]
        answer = ask(user, "Preciso regar amanhã?")

    assert answer == {"role": "ai", "message": "Vai chover, não precisa regar."}
    tavily.return_value.invoke.assert_called_once_with(
        input="previsão de chuva em Curitiba"
    )
    search_result = agents.web_answer.call_args.kwargs["messages"][-1]
    assert isinstance(search_result, ToolMessage)
    assert "Chuva amanhã" in search_result.content
    assert UserMemory.objects.get(user=user).memory == (
        "Mora em Curitiba e tem uma samambaia."
    )


def test_an_unknown_route_stops_the_chatbot() -> None:
    with pytest.raises(ValueError, match="update_memory"):
        nodes.route_picker(cast(SquadState, {"route": "update_memory"}))


def send_message(client: Client, message: str) -> tuple[int, Any]:
    response = client.post(
        "/api/chatbot/message",
        {"user_id": 7, "message": message},
        content_type="application/json",
        headers=bearer(user_token("plants", "7")),
    )
    return response.status_code, response.json()


def test_the_answer_comes_back_with_the_user_id(client: Client) -> None:
    with patch.object(ChatBotApi, "llm") as llm:
        llm.process_message.return_value.data = {"role": "ai", "message": "Arr!"}
        answer = send_message(client, "Oi")

    assert answer == (
        200,
        {"user_id": 7, "response": {"role": "ai", "message": "Arr!"}},
    )


def test_a_message_over_1000_characters_gets_400(client: Client) -> None:
    with patch.object(ChatBotApi, "llm") as llm:
        answer = send_message(client, "a" * 1001)

    assert answer == (400, {"error": "Invalid request data"})
    llm.process_message.assert_not_called()


def test_a_message_the_chatbot_cannot_answer_gets_400(client: Client) -> None:
    with patch.object(ChatBotApi, "llm") as llm:
        llm.process_message.return_value = None
        answer = send_message(client, "Oi")

    assert answer == (400, {"error": "Error processing user message"})

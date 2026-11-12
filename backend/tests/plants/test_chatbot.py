import json
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any, NamedTuple, cast
from unittest.mock import MagicMock, patch

import pytest
from django.test import Client
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.messages.tool import tool_call
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
from langchain_core.utils.function_calling import convert_to_openai_tool

from plants.api.chatbot import agents as chatbot_agents
from plants.api.chatbot import nodes, tools
from plants.api.chatbot.chatbot import LLM
from plants.api.chatbot.prompts import (
    CHAT_BOT_AGENT_PROMPT,
    ROUTER_AGENT_PROMPT,
    TOOLS_AGENT_PROMPT,
)
from plants.api.chatbot.routes import ChatBotApi
from plants.api.chatbot.schemas import ChatInfo, LLMAnswerSchema, Routing, SquadState
from plants.models import ChatHistory, Esp32Data, UserMemory, Users
from tests.api_tokens import bearer, saved_device, user_token

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

    with patch.object(tools, "TavilySearch") as tavily:
        tavily.return_value.invoke.return_value = {
            "results": [{"content": "Chuva amanhã"}]
        }
        answer = ask(user, "Preciso regar amanhã?")

    assert answer == {"role": "ai", "message": "Vai chover, não precisa regar."}
    tavily.return_value.invoke.assert_called_once_with(
        input="previsão de chuva em Curitiba"
    )
    search_result = agents.web_answer.call_args.kwargs["messages"][-1]
    assert isinstance(search_result, ToolMessage)
    assert "Chuva amanhã" in search_result.content
    assert saved_messages(user) == [
        ("human", "Preciso regar amanhã?"),
        ("ai", "Vai chover, não precisa regar."),
    ]
    assert UserMemory.objects.get(user=user).memory == (
        "Mora em Curitiba e tem uma samambaia."
    )


@DATABASES
def test_the_chatbot_gets_only_the_last_five_exchanges(agents: Agents) -> None:
    user = Users.objects.create(auth_user_id=1)
    for number in range(1, 7):
        ChatHistory.objects.create(
            user=user, role="human", message=f"Pergunta {number}"
        )
        ChatHistory.objects.create(user=user, role="ai", message=f"Resposta {number}")
    agents.chatbot.return_value = LLMAnswerSchema(reasoning="", message="Arr!")

    ask(user, "Pergunta 7")

    messages = agents.chatbot.call_args.kwargs["messages"]
    assert [message.content for message in messages] == [
        *[text for n in range(2, 7) for text in (f"Pergunta {n}", f"Resposta {n}")],
        "Pergunta 7",
    ]


def test_the_web_search_prints_nothing(capsys: pytest.CaptureFixture[str]) -> None:
    with patch.object(tools, "TavilySearch") as tavily:
        tavily.return_value.invoke.return_value = {
            "results": [{"content": "Chuva amanhã"}]
        }
        tools.web_search.invoke({"web_search_input": "previsão de chuva"})

    assert capsys.readouterr().out == ""


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


@pytest.mark.parametrize("prompt", [CHAT_BOT_AGENT_PROMPT, TOOLS_AGENT_PROMPT])
def test_the_answer_comes_in_the_user_s_language_in_a_plain_voice(
    prompt: ChatPromptTemplate,
) -> None:
    # The site is in Portuguese and English, and the assistant once spoke as a
    # pirate.
    system = prompt.format_messages(
        date="2026-11-10", user_memory="", input="Oi", agent_scratchpad=""
    )[0].content

    assert "same language as the user's latest message" in system
    assert "pirate" not in system


# The ToolNode runs each tool in a worker thread, whose database connection sees
# only committed rows: the tests that read the plants through it commit theirs.
COMMITTED = pytest.mark.django_db(databases=["default", "plants_db"], transaction=True)


def plant_reading(owner_device_nickname: str = "Manjericão") -> Users:
    """A person with one plant and one reading; returns the person."""
    device, _ = saved_device(owner_device_nickname)
    Esp32Data.objects.create(
        analog_value=2048, digital_value=1, user=device.user, device=device
    )
    return device.user


def search_call(call_id: str) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[
            tool_call(name="web_search", args={"web_search_input": "regar"}, id=call_id)
        ],
    )


def test_the_model_doesnt_see_the_user_id() -> None:
    # What OpenAI gets for each tool.
    readings = convert_to_openai_tool(tools.get_plant_readings)["function"]
    plants = convert_to_openai_tool(tools.list_my_plants)["function"]

    assert set(readings["parameters"]["properties"]) == {"plant", "hours"}
    assert plants["parameters"].get("properties", {}) == {}


@COMMITTED
def test_the_tools_read_only_the_conversation_s_person(agents: Agents) -> None:
    ana = plant_reading("Manjericão")
    bia, _ = saved_device("Manjericão")
    for _ in range(2):
        Esp32Data.objects.create(
            analog_value=1000, digital_value=1, user=bia.user, device=bia
        )
    agents.router.return_value = Routing(route="tools_agent")
    agents.web_search.return_value = AIMessage(
        content="",
        tool_calls=[tool_call(name="list_my_plants", args={}, id="call-1")],
    )
    agents.web_answer.return_value = AIMessage(content="Você tem um manjericão.")

    ask(ana, "Quais plantas eu tenho?")

    [result] = [
        m
        for m in agents.web_answer.call_args.kwargs["messages"]
        if isinstance(m, ToolMessage)
    ]
    content = result.content
    assert isinstance(content, str)
    [plant] = json.loads(content)["plants"]
    assert (plant["plant"], plant["readings"]) == ("Manjericão", 1)


@COMMITTED
def test_a_question_about_the_plants_can_take_several_tool_calls(
    agents: Agents,
) -> None:
    user = plant_reading()
    agents.router.return_value = Routing(route="tools_agent")
    agents.web_search.return_value = AIMessage(
        content="",
        tool_calls=[tool_call(name="list_my_plants", args={}, id="call-1")],
    )
    agents.web_answer.side_effect = [
        AIMessage(
            content="",
            tool_calls=[
                tool_call(
                    name="get_plant_readings",
                    args={"plant": "Manjericão", "hours": 24},
                    id="call-2",
                )
            ],
        ),
        AIMessage(content="O solo do manjericão está em 50%."),
    ]

    answer = ask(user, "Como está o meu manjericão?")

    assert answer == {"role": "ai", "message": "O solo do manjericão está em 50%."}
    last_call = agents.web_answer.call_args_list[-1].kwargs
    results = [m for m in last_call["messages"] if isinstance(m, ToolMessage)]
    assert [m.name for m in results] == ["list_my_plants", "get_plant_readings"]
    readings = results[1].content
    assert isinstance(readings, str)
    assert json.loads(readings)["measures"]["soil_percent"]["last"] == 50


@DATABASES
def test_the_tool_calls_stop_after_four_rounds(agents: Agents) -> None:
    user = Users.objects.create(auth_user_id=1)
    agents.router.return_value = Routing(route="tools_agent")
    agents.web_search.return_value = search_call("call-0")

    def respond(messages: list[Any], memory: str, allow_tools: bool) -> AIMessage:
        if allow_tools:
            return search_call(f"call-{len(messages)}")
        return AIMessage(content="Regue duas vezes por semana.")

    agents.web_answer.side_effect = respond

    with patch.object(tools, "TavilySearch") as tavily:
        tavily.return_value.invoke.return_value = {
            "results": [{"content": "Regar pouco"}]
        }
        answer = ask(user, "Quando devo regar?")

    assert answer == {"role": "ai", "message": "Regue duas vezes por semana."}
    assert [
        call.kwargs["allow_tools"] for call in agents.web_answer.call_args_list
    ] == [True, True, True, False]
    assert tavily.return_value.invoke.call_count == 4


def test_the_router_knows_plant_readings_are_for_the_tools() -> None:
    router = ROUTER_AGENT_PROMPT.format_messages(
        conversation=[HumanMessage(content="Oi")]
    )[0].content

    for text in [Routing.route_description, router]:
        assert "plants" in text
        assert "readings" in text


@COMMITTED
def test_a_person_without_plants_gets_an_answer_the_model_can_read(
    agents: Agents,
) -> None:
    # An empty list would reach OpenAI as an empty tool message, which it refuses.
    user = Users.objects.create(auth_user_id=1)
    agents.router.return_value = Routing(route="tools_agent")
    agents.web_search.return_value = AIMessage(
        content="",
        tool_calls=[tool_call(name="list_my_plants", args={}, id="call-1")],
    )
    agents.web_answer.return_value = AIMessage(content="Você ainda não tem sensores.")

    ask(user, "Como estão minhas plantas?")

    [result] = [
        m
        for m in agents.web_answer.call_args.kwargs["messages"]
        if isinstance(m, ToolMessage)
    ]
    content = result.content
    assert isinstance(content, str)
    assert json.loads(content) == {"plants": []}


def test_the_prompts_give_the_current_time_in_sao_paulo() -> None:
    """The tools give São Paulo times, so the prompts' "now" must be one too."""
    prompts: list[str] = []

    def heard(prompt: Any) -> AIMessage:
        prompts.append(prompt.to_messages()[0].content)
        return AIMessage(content="Oi")

    def answered(prompt: Any) -> dict[str, str]:
        heard(prompt)
        return {"reasoning": "-", "message": "Oi"}

    chatbot = MagicMock()
    chatbot.with_structured_output.return_value = RunnableLambda(answered)
    half_past_six_utc = datetime(2026, 11, 11, 18, 30, tzinfo=UTC)
    with (
        patch("django.utils.timezone.now", return_value=half_past_six_utc),
        patch.object(chatbot_agents, "llm_4", chatbot),
        patch.object(chatbot_agents, "llm_4_with_tools", RunnableLambda(heard)),
    ):
        chatbot_agents.call_tools_agent(HumanMessage(content="Oi"), "")
        chatbot_agents.call_tool_response_agent(
            [HumanMessage(content="Oi")], "", allow_tools=True
        )
        chatbot_agents.call_chatbot_agent([HumanMessage(content="Oi")], "")

    assert len(prompts) == 3
    for prompt in prompts:
        assert "2026-11-11 15:30 (São Paulo time)" in prompt


@DATABASES
def test_the_router_sees_the_previous_exchange(agents: Agents) -> None:
    user = Users.objects.create(auth_user_id=1)
    ChatHistory.objects.create(
        user=user, role="human", message="Como está o manjericão?"
    )
    ChatHistory.objects.create(user=user, role="ai", message="O solo está em 50%.")
    agents.chatbot.return_value = LLMAnswerSchema(reasoning="-", message="Ok")

    ask(user, "E nos últimos 7 dias?")

    seen = agents.router.call_args.kwargs["messages"]
    assert [m.content for m in seen] == [
        "Como está o manjericão?",
        "O solo está em 50%.",
        "E nos últimos 7 dias?",
    ]


@DATABASES
def test_the_tool_rounds_stop_even_if_the_model_keeps_asking(
    agents: Agents,
) -> None:
    user = Users.objects.create(auth_user_id=1)
    agents.router.return_value = Routing(route="tools_agent")
    agents.web_search.return_value = search_call("call-0")
    agents.web_answer.side_effect = lambda messages, memory, allow_tools: search_call(
        f"call-{len(messages)}"
    )

    with patch.object(tools, "TavilySearch") as tavily:
        tavily.return_value.invoke.return_value = {
            "results": [{"content": "Regar pouco"}]
        }
        ask(user, "Quando devo regar?")

    assert agents.web_answer.call_count == 4
    assert tavily.return_value.invoke.call_count == 4


@DATABASES
def test_a_failing_tool_doesnt_lose_the_answer(agents: Agents) -> None:
    user = Users.objects.create(auth_user_id=1)
    agents.router.return_value = Routing(route="tools_agent")
    agents.web_search.return_value = search_call("call-1")
    agents.web_answer.return_value = AIMessage(content="Não consegui buscar agora.")

    with patch.object(tools, "TavilySearch") as tavily:
        tavily.return_value.invoke.side_effect = RuntimeError("Tavily is down")
        answer = ask(user, "Vai chover amanhã?")

    assert answer == {"role": "ai", "message": "Não consegui buscar agora."}
    [result] = [
        m
        for m in agents.web_answer.call_args.kwargs["messages"]
        if isinstance(m, ToolMessage)
    ]
    assert "Tavily is down" in result.content


def test_the_web_search_asks_tavily_for_three_advanced_results() -> None:
    with patch.object(tools, "TavilySearch") as tavily:
        tavily.return_value.invoke.return_value = {"results": [{"content": "Chuva"}]}
        result = tools.web_search.invoke({"web_search_input": "chuva em Curitiba"})

    tavily.assert_called_once_with(max_results=3, search_depth="advanced")
    tavily.return_value.invoke.assert_called_once_with(input="chuva em Curitiba")
    assert result == {"results": [{"content": "Chuva"}]}

from collections.abc import Callable
from typing import Any, NamedTuple
from unittest.mock import patch

import pytest
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.messages.tool import invalid_tool_call, tool_call
from langchain_core.runnables import RunnableLambda
from langchain_core.tools import tool

from political_culture.api.chatbot import agents
from political_culture.api.chatbot.tools import user_tools
from political_culture.api.chatbot.utils import get_recent_chat_history_db
from political_culture.models import Texts, TextWordCount, Users

DATABASES = pytest.mark.django_db(databases=["default", "political_culture_db"])


@tool
def double(number: int) -> int:
    """Return the number times two."""
    return number * 2


@tool
def find_nothing() -> list[str]:
    """Return no results."""
    return []


@tool
def break_down() -> str:
    """Fail."""
    raise RuntimeError("database is down")


class ScriptedModel:
    """Stands in for the chat model: answers each call with the next scripted
    message and records the tool_choice and the messages of every call."""

    def __init__(self, answers: list[AIMessage]) -> None:
        self.answers = answers
        self.calls: list[tuple[Any, list[BaseMessage]]] = []

    def bind_tools(self, tools: list[Any], tool_choice: Any = None) -> "BoundModel":
        return BoundModel(self, tool_choice)


class BoundModel:
    def __init__(self, model: ScriptedModel, tool_choice: Any) -> None:
        self.model = model
        self.tool_choice = tool_choice

    def invoke(self, messages: list[BaseMessage]) -> AIMessage:
        self.model.calls.append((self.tool_choice, list(messages)))
        return self.model.answers.pop(0)


def asks_for(name: str, call_id: str, **args: Any) -> AIMessage:
    return AIMessage(
        content="", tool_calls=[tool_call(name=name, args=args, id=call_id)]
    )


def answer_with(
    monkeypatch: pytest.MonkeyPatch, answers: list[AIMessage], tools: list[Any]
) -> tuple[str, ScriptedModel]:
    model = ScriptedModel(answers)
    monkeypatch.setattr(agents, "llm_4", model)
    reply = agents._answer_with_tools([HumanMessage(content="Oi")], tools)
    return reply, model


def tool_reply(model: ScriptedModel) -> ToolMessage:
    _, messages = model.calls[1]
    reply = messages[-1]
    assert isinstance(reply, ToolMessage)
    return reply


def test_the_tools_the_model_asks_for_run_before_it_answers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reply, model = answer_with(
        monkeypatch,
        [asks_for("double", "call-1", number=21), AIMessage(content="Dá 42.")],
        [double],
    )

    assert reply == "Dá 42."
    _, messages = model.calls[1]
    assert [type(message) for message in messages] == [
        HumanMessage,
        AIMessage,
        ToolMessage,
    ]
    assert tool_reply(model).content == "42"
    assert tool_reply(model).tool_call_id == "call-1"


def test_after_the_last_round_the_model_answers_without_tools(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rounds = agents.MAX_TOOL_ROUNDS
    answers = [asks_for("double", f"call-{n}", number=n) for n in range(rounds)]

    reply, model = answer_with(
        monkeypatch, [*answers, AIMessage(content="Pronto.")], [double]
    )

    assert reply == "Pronto."
    choices = [choice for choice, _ in model.calls]
    assert choices == [None] * rounds + ["none"]


def test_an_empty_result_goes_back_as_json_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, model = answer_with(
        monkeypatch,
        [asks_for("find_nothing", "call-1"), AIMessage(content="Nada.")],
        [find_nothing],
    )

    assert tool_reply(model).content == "[]"


@pytest.mark.parametrize(
    ("answer", "message"),
    [
        (asks_for("break_down", "call-1"), "database is down"),
        (asks_for("word_count", "call-1"), "there is no tool named word_count"),
        (asks_for("double", "call-1", number="vinte"), "number"),
    ],
)
def test_a_failing_call_goes_back_to_the_model_as_an_error(
    monkeypatch: pytest.MonkeyPatch, answer: AIMessage, message: str
) -> None:
    reply, model = answer_with(
        monkeypatch, [answer, AIMessage(content="Não deu.")], [double, break_down]
    )

    assert reply == "Não deu."
    assert tool_reply(model).status == "error"
    assert message in str(tool_reply(model).content)


def test_a_call_with_broken_arguments_still_gets_a_reply(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    broken = invalid_tool_call(
        name="double", args="{number", id="call-1", error="invalid JSON"
    )
    reply, model = answer_with(
        monkeypatch,
        [AIMessage(content="", invalid_tool_calls=[broken]), AIMessage(content="Ok.")],
        [double],
    )

    assert reply == "Ok."
    assert tool_reply(model).tool_call_id == "call-1"
    assert tool_reply(model).status == "error"


def test_the_model_cannot_pick_the_user_of_the_user_tools() -> None:
    for scoped_tool in user_tools(7):
        assert "user_id" not in scoped_tool.args


def test_the_memory_tool_reads_the_user_of_the_conversation() -> None:
    with patch("political_culture.api.chatbot.tools.UserMemory.objects") as memories:
        memories.filter.return_value.values_list.return_value.first.return_value = (
            "Gosta de história."
        )

        memory = user_tools(7).memory.invoke({})

    assert memory == "Gosta de história."
    memories.filter.assert_called_once_with(user_id=7)


class Library(NamedTuple):
    """User me's view of the library: one text ticked by me, one ticked only by
    another user, one ticked by no one, and a text each of them pasted in the chat."""

    me: int
    ticked: Texts
    ticked_by_other: Texts
    unticked: Texts
    my_paste: Texts
    other_paste: Texts


@pytest.fixture
def library() -> Library:
    me = Users.objects.create(auth_user_id=1)
    other = Users.objects.create(auth_user_id=2)

    def text(title: str, owner: Users, pasted: bool = False) -> Texts:
        text = Texts.objects.create(
            user=owner, title=title, text=title, user_submitted_text=pasted
        )
        TextWordCount.objects.create(
            text=text, total_word_count=1, word_frequencies={title: 1}
        )
        return text

    ticked = text("Marcado", other)
    ticked_by_other = text("Marcado pelo outro", me)
    ticked.selected_by.add(me)
    ticked_by_other.selected_by.add(other)
    return Library(
        me.id,
        ticked,
        ticked_by_other,
        text("Desmarcado", other),
        text("Meu colado", me, pasted=True),
        text("Colado pelo outro", other, pasted=True),
    )


@DATABASES
def test_the_library_tool_lists_only_the_texts_the_user_ticked(
    library: Library,
) -> None:
    texts = user_tools(library.me).library_texts.invoke({})

    assert [text[0] for text in texts] == [library.ticked.id]


@DATABASES
def test_word_counts_come_from_ticked_texts_and_the_user_own_pastes(
    library: Library,
) -> None:
    word_count = user_tools(library.me).word_count

    readable = {
        text.title
        for text in library[1:]
        if word_count.invoke({"text_id": text.id}) is not None
    }

    assert readable == {"Marcado", "Meu colado"}


@DATABASES
def test_the_text_search_reads_ticked_texts_and_the_user_own_pastes(
    library: Library,
) -> None:
    # CosineDistance needs PostgreSQL, so only the filter runs on the database.
    with (
        patch("political_culture.api.chatbot.tools.OpenAIEmbeddings"),
        patch("political_culture.api.chatbot.tools.TextChunks.objects") as chunks,
    ):
        user_tools(library.me).search_text.invoke({"text_id": 1, "query": "estado"})

    searched = chunks.filter.call_args.kwargs["text__in"]
    assert set(searched.values_list("title", flat=True)) == {"Marcado", "Meu colado"}


@DATABASES
@pytest.mark.parametrize(
    "agent",
    [
        agents.word_analyist_agent,
        agents.text_analyist_agent,
        agents.text_ideology_analyist_agent,
    ],
)
def test_the_analysis_agents_read_the_library_as_the_user(
    library: Library, agent: Callable[[str, int], str]
) -> None:
    with patch.object(agents, "_invoke_tool_agent", return_value="Ok.") as invoke:
        agent("Um texto.", library.me)

    tools = {tool.name: tool for tool in invoke.call_args.args[1]}
    listed = tools["get_all_texts_info"].invoke({})
    assert [text[0] for text in listed] == [library.ticked.id]


class Row:
    def __init__(self, message: str) -> None:
        self.message = message


class FakeHistory:
    """Answers ChatHistory.objects.filter(...).order_by("-id")[:5] with the rows
    of the requested role, newest first, as the database would."""

    def __init__(self, newest_first: dict[str, list[Row]]) -> None:
        self.newest_first = newest_first
        self.role = ""

    def filter(self, user_id: int, role: str) -> "FakeHistory":
        self.role = role
        return self

    def order_by(self, field: str) -> "FakeHistory":
        assert field == "-id"
        return self

    def __getitem__(self, key: slice) -> list[Row]:
        return self.newest_first[self.role][key]


def test_the_recent_history_is_the_last_exchanges_oldest_first() -> None:
    history = FakeHistory(
        {
            "human": [Row(f"pergunta {n}") for n in range(9, 0, -1)],
            "ai": [Row(f"resposta {n}") for n in range(9, 0, -1)],
        }
    )
    with patch("political_culture.api.chatbot.utils.ChatHistory.objects", history):
        messages = get_recent_chat_history_db(7)

    assert [message.content for message in messages[:2]] == [
        "pergunta 5",
        "resposta 5",
    ]
    assert [message.content for message in messages[-2:]] == [
        "pergunta 9",
        "resposta 9",
    ]


def test_the_memory_summary_starts_from_the_stored_memory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    received: list[str] = []

    def summarize(prompt: Any) -> dict[str, str]:
        received.append(prompt.to_string())
        return {"info": "Gosta de história e de política."}

    class SummaryModel:
        def with_structured_output(self, **_kwargs: Any) -> RunnableLambda[Any, Any]:
            return RunnableLambda(summarize)

    monkeypatch.setattr(agents, "llm_4", SummaryModel())

    info = agents.call_user_info_agent("E política?", [], "Gosta de história.")

    assert info.info == "Gosta de história e de política."
    assert "Current memory: Gosta de história." in received[0]

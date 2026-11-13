import asyncio
import json
import logging
from collections.abc import Callable
from typing import Any

import aiohttp
import httpx
import pytest
from google.genai import errors as genai_errors
from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableBinding
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_google_genai.chat_models import (
    ChatGoogleGenerativeAIError,
    GoogleAPIError,
    GoogleAuthenticationError,
    GoogleInvalidRequestError,
    GoogleModelNotFoundError,
    GoogleRateLimitError,
)
from langchain_openai import ChatOpenAI
from langchain_openai.chat_models.base import (
    OpenAIRateLimitError,
    OpenAITimeoutError,
)
from pydantic import BaseModel
from pytest_django import Settings

from news_podcast.api.core import llm
from news_podcast.api.core.config import (
    MAX_OUTPUT_TOKENS,
    TEXT_RETRY_MINUTES,
    THINKING_LEVEL,
)
from news_podcast.api.core.gemini import (
    MAX_ATTEMPTS,
    RATE_LIMIT_WAIT_SECONDS,
    backoff_seconds,
)
from news_podcast.api.core.llm import (
    BadAnswerError,
    TextError,
    TextModels,
    chat_model,
    split_model,
    structured_model,
)
from news_podcast.api.core.schemas import Script, Turn, Usage
from news_podcast.api.episode.schemas import StorySelection
from tests.news_podcast.fake_models import FakeChatModel, fake_factory

MAIN = "gemini-3.8-flash"
FALLBACK = "gemini-3.6-flash"
OPENAI = "openai:gpt-4.1-mini"
PROMPT = ChatPromptTemplate.from_messages(
    [("system", "Responda {what}."), ("human", "{material}")]
)
VALUES = {"what": "em JSON", "material": "o material"}
ANSWER = '{"ok": true}'
GEMINI_URL = "https://generativelanguage.googleapis.com"
OPENAI_URL = "https://api.openai.com/v1/chat/completions"


class Answer(BaseModel):
    ok: bool


def gemini_body(code: int, status: str, details: list[Any]) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": f"{status}: the model is busy",
            "status": status,
            "details": details,
        }
    }


def gemini_rate_limit(quota_id: str, retry_delay: str | None = None) -> Exception:
    """A Gemini 429 as langchain-google-genai raises it: GoogleRateLimitError, from
    the SDK's ClientError, which carries the recorded body."""
    details: list[Any] = [
        {
            "@type": "type.googleapis.com/google.rpc.QuotaFailure",
            "violations": [{"quotaId": quota_id}],
        }
    ]
    if retry_delay:
        details.append(
            {
                "@type": "type.googleapis.com/google.rpc.RetryInfo",
                "retryDelay": retry_delay,
            }
        )
    cause = genai_errors.ClientError(
        429, gemini_body(429, "RESOURCE_EXHAUSTED", details)
    )
    error = GoogleRateLimitError(f"Error calling model '{MAIN}' (429): {cause}")
    error.__cause__ = cause
    return error


def gemini_not_found() -> Exception:
    cause = genai_errors.ClientError(404, gemini_body(404, "NOT_FOUND", []))
    error = GoogleModelNotFoundError(f"Error calling model '{MAIN}' (404): {cause}")
    error.__cause__ = cause
    return error


def gemini_overloaded() -> Exception:
    return GoogleAPIError(503, gemini_body(503, "UNAVAILABLE", []))


def openai_rate_limit(code: str, retry_after: str | None = None) -> Exception:
    headers = {"retry-after": retry_after} if retry_after else {}
    response = httpx.Response(
        429, headers=headers, request=httpx.Request("POST", OPENAI_URL)
    )
    body = {"message": "Rate limit reached", "type": code, "param": None, "code": code}
    return OpenAIRateLimitError(
        message=f"Error code: 429 - {body}", response=response, body=body
    )


DAILY_QUOTA = gemini_rate_limit("GenerateRequestsPerDayPerProjectPerModel-FreeTier")
BUSY = gemini_overloaded()


def record_waits(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    waits: list[float] = []

    async def record(seconds: float) -> None:
        waits.append(seconds)

    monkeypatch.setattr(asyncio, "sleep", record)
    return waits


@pytest.fixture(autouse=True)
def keys(settings: Settings) -> None:
    settings.GEMINI_API_KEY = "gemini-test-key"
    settings.OPENAI_API_KEY = "openai-test-key"


def ask_scripted(
    outcomes: dict[str, list[Any]],
    *,
    names: tuple[str, ...] = (MAIN, FALLBACK),
    check: Callable[[Answer], Any] = lambda answer: answer,
    wait: bool = True,
    usages: list[Usage] | None = None,
) -> tuple[list[str], TextError | None]:
    """Asks for one answer; returns the models asked, call by call, and the error."""
    asked: list[str] = []

    async def scenario() -> TextError | None:
        async with httpx.AsyncClient() as client:
            text = TextModels(
                names,
                [] if usages is None else usages,
                client,
                fake_factory(outcomes, asked),
            )
            try:
                await text.ask(
                    PROMPT,
                    VALUES,
                    step="selection",
                    schema=Answer,
                    check=check,
                    wait=wait,
                )
            except TextError as error:
                return error
            return None

    return asked, asyncio.run(scenario())


def test_split_model_reads_bare_and_prefixed_names() -> None:
    assert split_model("gemini-3.8-flash") == ("google_genai", "gemini-3.8-flash")
    assert split_model("google_genai:gemini-3.8-flash") == (
        "google_genai",
        "gemini-3.8-flash",
    )
    assert split_model("openai:gpt-4.1-mini") == ("openai", "gpt-4.1-mini")
    assert split_model("anthropic:claude-x") == ("anthropic", "claude-x")
    assert split_model("gpt-4.1-mini") == ("", "gpt-4.1-mini")


def test_a_bare_gemini_name_is_built_as_google_genai(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, dict[str, Any]]] = []

    def record(model: str, **kwargs: Any) -> BaseChatModel:
        calls.append((model, kwargs))
        return FakeChatModel(model=model, outcomes=[], asked=[])

    monkeypatch.setattr(llm, "init_chat_model", record)

    async def scenario() -> None:
        async with httpx.AsyncClient() as client:
            TextModels([MAIN], [], client).model(MAIN)

    asyncio.run(scenario())

    [(model, options)] = calls
    assert model == "gemini-3.8-flash"
    assert options["model_provider"] == "google_genai"
    assert options["api_key"] == "gemini-test-key"


def test_the_built_models_keep_our_retries_and_limits() -> None:
    async def scenario() -> tuple[BaseChatModel, BaseChatModel, httpx.AsyncClient]:
        async with httpx.AsyncClient() as client:
            gemini = chat_model("google_genai", "gemini-3.8-flash", "dummy", client)
            openai = chat_model("openai", "gpt-4.1-mini", "dummy", client)
            return gemini, openai, client

    gemini, openai, client = asyncio.run(scenario())

    assert isinstance(gemini, ChatGoogleGenerativeAI)
    assert gemini.max_retries == 1
    assert gemini.max_output_tokens == MAX_OUTPUT_TOKENS == 32768
    assert gemini.reasoning_effort == THINKING_LEVEL == "medium"
    assert gemini.timeout == 180
    assert isinstance(openai, ChatOpenAI)
    assert openai.max_retries == 0
    assert openai.max_tokens is None
    assert openai.reasoning_effort is None
    assert openai.request_timeout == 180
    assert openai.http_async_client is client


def bound_kwargs(runnable: Any) -> dict[str, Any]:
    """The kwargs of the binding inside a structured-output runnable."""
    if isinstance(runnable, RunnableBinding):
        return dict(runnable.kwargs)
    children: list[Any] = []
    for attribute in ("first", "middle", "last", "steps__", "bound"):
        value = getattr(runnable, attribute, None)
        if isinstance(value, dict):
            children.extend(value.values())
        elif isinstance(value, list):
            children.extend(value)
        elif value is not None:
            children.append(value)
    for child in children:
        found = bound_kwargs(child)
        if found:
            return found
    return {}


def required_fields(schema: dict[str, Any], definition: str) -> set[str]:
    return set(schema["$defs"][definition]["required"])


def test_each_provider_gets_the_serialization_schema_with_every_field_required() -> (
    None
):
    async def scenario() -> list[dict[str, Any]]:
        async with httpx.AsyncClient() as client:
            gemini = chat_model("google_genai", "gemini-3.8-flash", "dummy", client)
            openai = chat_model("openai", "gpt-4.1-mini", "dummy", client)
            return [
                bound_kwargs(structured_model(model, schema))
                for model in (gemini, openai)
                for schema in (StorySelection, Script)
            ]

    gemini_story, gemini_script, openai_story, openai_script = asyncio.run(scenario())

    for kwargs in (gemini_story, gemini_script, openai_story, openai_script):
        assert (
            kwargs["ls_structured_output_format"]["kwargs"]["method"] == "json_schema"
        )
    story_fields = {"title", "category", "minutes", "angle", "item_ids"}
    turn_fields = {"speaker", "text", "headline"}
    assert gemini_story["response_json_schema"] == StorySelection.model_json_schema(
        mode="serialization"
    )
    assert required_fields(gemini_story["response_json_schema"], "SelectedStory") == (
        story_fields
    )
    assert required_fields(gemini_script["response_json_schema"], "Turn") == turn_fields
    openai_story_schema = openai_story["response_format"]["json_schema"]
    openai_script_schema = openai_script["response_format"]["json_schema"]
    assert openai_story_schema["strict"] is False
    assert required_fields(openai_story_schema["schema"], "SelectedStory") == (
        story_fields
    )
    assert required_fields(openai_script_schema["schema"], "Turn") == turn_fields


def test_a_good_answer_returns_what_the_check_returns() -> None:
    usages: list[Usage] = []
    asked: list[str] = []
    built: dict[str, FakeChatModel] = {}

    async def scenario() -> str:
        async with httpx.AsyncClient() as client:
            text = TextModels(
                [MAIN, FALLBACK],
                usages,
                client,
                fake_factory({MAIN: [ANSWER], FALLBACK: []}, asked, built),
            )
            return await text.ask(
                PROMPT,
                VALUES,
                step="selection",
                schema=Answer,
                check=lambda answer: f"checked {answer.ok}",
            )

    assert asyncio.run(scenario()) == "checked True"
    assert asked == [MAIN]
    assert usages == [
        Usage(step="selection", model=MAIN, input_tokens=100, output_tokens=15)
    ]
    [bound] = built[MAIN].bound
    assert bound == {
        "schema": Answer.model_json_schema(mode="serialization"),
        "include_raw": True,
        "method": "json_schema",
    }
    [messages] = built[MAIN].received
    assert [(message.type, message.content) for message in messages] == [
        ("system", "Responda em JSON."),
        ("human", "o material"),
    ]


def test_text_skips_the_main_model_once_it_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record_waits(monkeypatch)
    asked: list[str] = []

    async def scenario() -> None:
        async with httpx.AsyncClient() as client:
            text = TextModels(
                [MAIN, FALLBACK],
                [],
                client,
                fake_factory(
                    {MAIN: [BUSY] * MAX_ATTEMPTS, FALLBACK: [ANSWER] * 2}, asked
                ),
            )
            for step in ("selection", "script"):
                await text.ask(
                    PROMPT,
                    VALUES,
                    step=step,
                    schema=Answer,
                    check=lambda answer: answer,
                )

    asyncio.run(scenario())

    assert asked == [MAIN] * MAX_ATTEMPTS + [FALLBACK, FALLBACK]


def test_a_broken_answer_is_asked_again_once() -> None:
    asked, error = ask_scripted({MAIN: ['{"ok": ', ANSWER], FALLBACK: []})

    assert error is None
    assert asked == [MAIN, MAIN]


def test_an_answer_that_fails_the_schema_is_asked_again_then_the_next_model() -> None:
    asked, error = ask_scripted({MAIN: ['{"ok": "talvez"}', "{}"], FALLBACK: [ANSWER]})

    assert error is None
    assert asked == [MAIN, MAIN, FALLBACK]


def test_a_selection_or_a_turn_that_breaks_the_schema_is_a_bad_answer() -> None:
    story = {
        "title": "T",
        "category": "geral",
        "minutes": 0,
        "angle": "",
        "item_ids": [],
    }
    asked: list[str] = []

    async def scenario() -> tuple[StorySelection, Script]:
        async with httpx.AsyncClient() as client:
            text = TextModels(
                [MAIN],
                [],
                client,
                fake_factory(
                    {
                        MAIN: [
                            json.dumps({"stories": [story]}),
                            json.dumps({"stories": [{**story, "minutes": 2}]}),
                            json.dumps(
                                {"turns": [{"speaker": "Bia", "headline": False}]}
                            ),
                            json.dumps({"turns": []}),
                        ]
                    },
                    asked,
                ),
            )
            selection = await text.ask(
                PROMPT,
                VALUES,
                step="selection",
                schema=StorySelection,
                check=lambda s: s,
            )
            script = await text.ask(
                PROMPT, VALUES, step="script", schema=Script, check=lambda s: s
            )
            return selection, script

    selection, script = asyncio.run(scenario())

    assert selection.stories[0].minutes == 2
    assert script.turns == []
    assert asked == [MAIN] * 4


def test_bad_answers_fail_at_once_with_no_model_down(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    waits = record_waits(monkeypatch)

    def reject(answer: Answer) -> Answer:
        raise BadAnswerError("a seleção veio sem notícias válidas")

    asked, error = ask_scripted(
        {MAIN: [ANSWER, ANSWER], FALLBACK: [ANSWER, ANSWER]}, check=reject
    )

    assert asked == [MAIN, MAIN, FALLBACK, FALLBACK]
    assert waits == []
    assert str(error) == " | ".join(
        [f"{MAIN}: a seleção veio sem notícias válidas"] * 2
        + [f"{FALLBACK}: a seleção veio sem notícias válidas"] * 2
    )


def test_an_empty_answer_is_a_bad_answer() -> None:
    asked, error = ask_scripted({MAIN: ["", ANSWER], FALLBACK: []})

    assert error is None
    assert asked == [MAIN, MAIN]


def test_broken_answers_still_count_in_the_cost() -> None:
    usages: list[Usage] = []

    def reject(answer: Answer) -> Answer:
        raise BadAnswerError("não serve")

    _, error = ask_scripted(
        {MAIN: ['{"ok": ', '{"ok": "x"}'], FALLBACK: [ANSWER, ANSWER]},
        check=reject,
        usages=usages,
    )

    assert error is not None
    assert "JSON inválido" in str(error)
    assert [(usage.step, usage.model) for usage in usages] == [
        ("selection", MAIN),
        ("selection", MAIN),
        ("selection", FALLBACK),
        ("selection", FALLBACK),
    ]
    assert all(usage.input_tokens == 100 for usage in usages)
    assert all(usage.output_tokens == 15 for usage in usages)


def test_an_answer_without_usage_counts_zero_tokens_with_a_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    usages: list[Usage] = []
    asked: list[str] = []

    def no_usage(
        provider: str, model: str, api_key: str, http_client: httpx.AsyncClient
    ) -> BaseChatModel:
        return FakeChatModel(model=model, outcomes=[ANSWER], asked=asked, usage=None)

    async def scenario() -> Answer:
        async with httpx.AsyncClient() as client:
            text = TextModels([MAIN], usages, client, no_usage)
            return await text.ask(
                PROMPT, VALUES, step="script", schema=Answer, check=lambda a: a
            )

    with caplog.at_level(logging.WARNING):
        answer = asyncio.run(scenario())

    assert answer.ok is True
    assert usages == [Usage(step="script", model=MAIN)]
    assert MAIN in caplog.text
    assert "script" in caplog.text


def test_a_cut_short_answer_is_logged_with_its_reason_and_where_it_breaks(
    caplog: pytest.LogCaptureFixture,
) -> None:
    broken = '{"turns": [{"speaker": "Bia", "text": "O ministro disse "não"."}]}'
    asked: list[str] = []

    def cut_short(
        provider: str, model: str, api_key: str, http_client: httpx.AsyncClient
    ) -> BaseChatModel:
        return FakeChatModel(
            model=model,
            outcomes=[broken, broken],
            asked=asked,
            finish_reason="MAX_TOKENS",
        )

    async def scenario() -> None:
        async with httpx.AsyncClient() as client:
            text = TextModels([MAIN], [], client, cut_short)
            await text.ask(
                PROMPT, VALUES, step="script", schema=Answer, check=lambda a: a
            )

    with (
        caplog.at_level(logging.WARNING),
        pytest.raises(TextError, match="JSON inválido"),
    ):
        asyncio.run(scenario())

    assert "MAX_TOKENS" in caplog.text
    assert f"{MAIN} (script)" in caplog.text
    assert "Expecting ',' delimiter" in caplog.text
    assert 'disse "não"' in caplog.text


def test_text_waits_and_asks_every_model_again_when_none_answers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    waits = record_waits(monkeypatch)
    timeout = TimeoutError()

    asked, error = ask_scripted({MAIN: [timeout, timeout], FALLBACK: [timeout, ANSWER]})

    assert error is None
    assert waits == [TEXT_RETRY_MINUTES[0] * 60]
    assert asked == [MAIN, FALLBACK, MAIN, FALLBACK]


def test_text_gives_up_after_the_last_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    waits = record_waits(monkeypatch)
    rounds = len(TEXT_RETRY_MINUTES) + 1
    timeout = TimeoutError()

    _, error = ask_scripted({MAIN: [timeout] * rounds, FALLBACK: [timeout] * rounds})

    assert error is not None
    assert waits == [minutes * 60 for minutes in TEXT_RETRY_MINUTES]
    assert (
        str(error)
        == f"{MAIN}: não respondeu em 180s | {FALLBACK}: não respondeu em 180s"
    )


def test_the_text_waits_are_shared_by_the_whole_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    waits = record_waits(monkeypatch)
    timeout = TimeoutError()
    asked: list[str] = []

    async def scenario() -> TextError | None:
        async with httpx.AsyncClient() as client:
            text = TextModels(
                [MAIN, FALLBACK],
                [],
                client,
                fake_factory(
                    {
                        MAIN: [timeout] * 3,
                        FALLBACK: [timeout, timeout, ANSWER, timeout],
                    },
                    asked,
                ),
            )
            await text.ask(
                PROMPT, VALUES, step="selection", schema=Answer, check=lambda a: a
            )
            try:
                await text.ask(
                    PROMPT, VALUES, step="script", schema=Answer, check=lambda a: a
                )
            except TextError as error:
                return error
            return None

    error = asyncio.run(scenario())

    assert error is not None
    assert waits == [minutes * 60 for minutes in TEXT_RETRY_MINUTES]


def test_one_round_and_no_wait_when_asked_not_to_wait(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    waits = record_waits(monkeypatch)
    timeout = TimeoutError()

    asked, error = ask_scripted({MAIN: [timeout], FALLBACK: [timeout]}, wait=False)

    assert error is not None
    assert waits == []
    assert asked == [MAIN, FALLBACK]


@pytest.mark.parametrize(
    "quota",
    [DAILY_QUOTA, openai_rate_limit("insufficient_quota", retry_after="1")],
    ids=["gemini-per-day", "openai-insufficient-quota"],
)
def test_a_model_out_of_quota_is_dropped_for_the_run_without_waiting(
    monkeypatch: pytest.MonkeyPatch, quota: Exception
) -> None:
    waits = record_waits(monkeypatch)

    asked, error = ask_scripted({MAIN: [quota], FALLBACK: [quota]})

    assert error is not None
    assert asked == [MAIN, FALLBACK]
    assert waits == []


def test_a_model_out_of_quota_is_not_asked_again_after_the_wait(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record_waits(monkeypatch)

    asked, error = ask_scripted(
        {MAIN: [DAILY_QUOTA], FALLBACK: [TimeoutError(), ANSWER]}
    )

    assert error is None
    assert asked == [MAIN, FALLBACK, FALLBACK]


@pytest.mark.parametrize(
    ("failure", "first_wait"),
    [
        (gemini_rate_limit("GenerateRequestsPerMinutePerProject", "7s"), 8.0),
        (
            gemini_rate_limit("GenerateRequestsPerMinutePerProject"),
            RATE_LIMIT_WAIT_SECONDS,
        ),
        (gemini_overloaded(), backoff_seconds(1)),
        (aiohttp.ServerDisconnectedError(), backoff_seconds(1)),
        (openai_rate_limit("rate_limit_exceeded", retry_after="7"), 8.0),
    ],
    ids=[
        "gemini-retry-delay",
        "gemini-per-minute",
        "gemini-503",
        "connection",
        "openai-retry-after",
    ],
)
def test_a_passing_failure_is_tried_again_after_a_wait(
    monkeypatch: pytest.MonkeyPatch, failure: Exception, first_wait: float
) -> None:
    waits = record_waits(monkeypatch)

    asked, error = ask_scripted({MAIN: [failure, ANSWER], FALLBACK: []})

    assert error is None
    assert asked == [MAIN, MAIN]
    assert waits == [first_wait]


def test_a_rate_limit_waits_longer_at_each_attempt_and_then_the_model_is_down(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    waits = record_waits(monkeypatch)
    per_minute = gemini_rate_limit("GenerateRequestsPerMinutePerProject")

    asked, error = ask_scripted({MAIN: [per_minute] * MAX_ATTEMPTS, FALLBACK: [ANSWER]})

    assert error is None
    assert asked == [MAIN] * MAX_ATTEMPTS + [FALLBACK]
    assert waits == [
        RATE_LIMIT_WAIT_SECONDS * attempt for attempt in range(1, MAX_ATTEMPTS)
    ]


@pytest.mark.parametrize(
    "timeout",
    [TimeoutError(), OpenAITimeoutError(request=httpx.Request("POST", OPENAI_URL))],
    ids=["gemini", "openai"],
)
def test_a_timeout_is_not_tried_again_and_the_model_is_down_at_once(
    monkeypatch: pytest.MonkeyPatch, timeout: Exception
) -> None:
    waits = record_waits(monkeypatch)

    asked, error = ask_scripted({MAIN: [timeout], FALLBACK: [ANSWER]})

    assert error is None
    assert asked == [MAIN, FALLBACK]
    assert waits == []


def test_a_refused_model_is_dropped_for_the_run_with_the_providers_message(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    record_waits(monkeypatch)
    asked: list[str] = []

    async def scenario() -> TextError | None:
        async with httpx.AsyncClient() as client:
            text = TextModels(
                [MAIN, FALLBACK],
                [],
                client,
                fake_factory(
                    {
                        MAIN: [gemini_not_found()],
                        FALLBACK: [TimeoutError(), ANSWER, ANSWER],
                    },
                    asked,
                ),
            )
            await text.ask(
                PROMPT, VALUES, step="selection", schema=Answer, check=lambda a: a
            )
            await text.ask(
                PROMPT, VALUES, step="script", schema=Answer, check=lambda a: a
            )
            return None

    with caplog.at_level(logging.WARNING):
        asyncio.run(scenario())

    assert asked == [MAIN, FALLBACK, FALLBACK, FALLBACK]
    assert "NOT_FOUND" in caplog.text


@pytest.mark.parametrize(
    "name",
    [
        "anthropic:claude-x",
        "google_vertexai:gemini-3.8-flash",
        "gpt-4.1-mini",
        "openai:",
        "openai: gpt-4.1-mini",
    ],
)
def test_a_model_with_an_unknown_provider_is_refused_and_the_fallback_answers(
    name: str,
) -> None:
    asked, error = ask_scripted({FALLBACK: [ANSWER]}, names=(name, FALLBACK))

    assert error is None
    assert asked == [FALLBACK]


@pytest.mark.parametrize(
    "failure",
    [ImportError("Unable to import langchain_google_genai"), ValueError("bad option")],
    ids=["missing-integration", "bad-option"],
)
def test_a_model_that_cannot_be_built_is_refused(failure: Exception) -> None:
    asked: list[str] = []

    def missing(
        provider: str, model: str, api_key: str, http_client: httpx.AsyncClient
    ) -> BaseChatModel:
        if model == MAIN:
            raise failure
        return FakeChatModel(model=model, outcomes=[ANSWER], asked=asked)

    async def scenario() -> Answer:
        async with httpx.AsyncClient() as client:
            text = TextModels([MAIN, FALLBACK], [], client, missing)
            return await text.ask(
                PROMPT, VALUES, step="selection", schema=Answer, check=lambda a: a
            )

    assert asyncio.run(scenario()).ok is True
    assert asked == [FALLBACK]


def test_an_openai_model_without_its_key_in_the_settings_is_refused(
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
    caplog: pytest.LogCaptureFixture,
) -> None:
    record_waits(monkeypatch)
    settings.OPENAI_API_KEY = None
    monkeypatch.setenv("OPENAI_API_KEY", "from-the-environment")

    with caplog.at_level(logging.WARNING):
        asked, error = ask_scripted(
            {"gemini-3.8-flash": [BUSY] * MAX_ATTEMPTS + [ANSWER]},
            names=(MAIN, OPENAI),
        )

    assert error is None
    assert asked == [MAIN] * (MAX_ATTEMPTS + 1)
    assert "OPENAI_API_KEY" in caplog.text


def test_without_the_gemini_key_no_request_is_made_and_nothing_waits(
    monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    waits = record_waits(monkeypatch)
    settings.GEMINI_API_KEY = None

    asked, error = ask_scripted({MAIN: [ANSWER], FALLBACK: [ANSWER]})

    assert asked == []
    assert waits == []
    assert str(error) == (
        f"{MAIN}: GEMINI_API_KEY não configurada | "
        f"{FALLBACK}: GEMINI_API_KEY não configurada"
    )


def test_the_gemini_key_comes_from_the_settings_not_the_environment(
    monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", "from-the-environment")
    settings.GEMINI_API_KEY = "from-the-settings"

    async def scenario() -> BaseChatModel:
        async with httpx.AsyncClient() as client:
            return TextModels([MAIN], [], client).model(MAIN)

    model = asyncio.run(scenario())

    assert isinstance(model, ChatGoogleGenerativeAI)
    assert model.google_api_key is not None
    assert model.google_api_key.get_secret_value() == "from-the-settings"


def gemini_client_error(
    error_class: type[Exception], code: int, status: str
) -> Exception:
    """A Gemini 4xx as langchain-google-genai raises it, from the SDK's ClientError."""
    cause = genai_errors.ClientError(code, gemini_body(code, status, []))
    error = error_class(f"Error calling model '{MAIN}' ({status}): {cause}")
    error.__cause__ = cause
    return error


def test_a_cut_answer_is_asked_again_even_when_its_json_could_be_closed() -> None:
    script = Script(turns=[Turn(speaker="Bia", text="O STF decidiu hoje")] * 3)
    complete = script.model_dump_json()
    cut = complete[: complete.rindex("decidiu")]
    asked: list[str] = []

    async def scenario() -> Script:
        async with httpx.AsyncClient() as client:
            text = TextModels(
                [MAIN], [], client, fake_factory({MAIN: [cut, complete]}, asked)
            )
            return await text.ask(
                PROMPT, VALUES, step="script", schema=Script, check=lambda s: s
            )

    assert asyncio.run(scenario()) == script
    assert asked == [MAIN, MAIN]


def test_an_error_the_sorting_does_not_know_lets_the_next_model_answer(
    caplog: pytest.LogCaptureFixture,
) -> None:
    unknown = RuntimeError("corpo de erro ilegível")

    with caplog.at_level(logging.ERROR):
        asked, error = ask_scripted({MAIN: [unknown, unknown], FALLBACK: [ANSWER]})

    assert error is None
    assert asked == [MAIN, MAIN, FALLBACK]
    assert "corpo de erro ilegível" in caplog.text


@pytest.mark.parametrize(
    ("failure", "expected"),
    [
        (
            GoogleAPIError(501, gemini_body(501, "NOT_IMPLEMENTED", [])),
            [MAIN, MAIN, FALLBACK],
        ),
        (
            GoogleAPIError(403, gemini_body(403, "PERMISSION_DENIED", [])),
            [MAIN, FALLBACK],
        ),
    ],
    ids=["a-5xx-that-does-not-pass", "a-4xx-in-a-server-error-class"],
)
def test_only_the_statuses_that_pass_are_tried_again(
    monkeypatch: pytest.MonkeyPatch, failure: Exception, expected: list[str]
) -> None:
    waits = record_waits(monkeypatch)

    asked, error = ask_scripted({MAIN: [failure, failure], FALLBACK: [ANSWER]})

    assert error is None
    assert asked == expected
    assert waits == []


def test_a_request_timeout_from_the_provider_marks_the_model_down(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    waits = record_waits(monkeypatch)
    request_timeout = gemini_client_error(
        ChatGoogleGenerativeAIError, 408, "DEADLINE_EXCEEDED"
    )

    asked, error = ask_scripted(
        {MAIN: [request_timeout, ANSWER], FALLBACK: [TimeoutError()]}
    )

    assert error is None
    assert asked == [MAIN, FALLBACK, MAIN]
    assert waits == [TEXT_RETRY_MINUTES[0] * 60]


@pytest.mark.parametrize(
    "refusal",
    [
        gemini_client_error(GoogleInvalidRequestError, 400, "INVALID_ARGUMENT"),
        gemini_client_error(GoogleAuthenticationError, 401, "UNAUTHENTICATED"),
        gemini_client_error(GoogleModelNotFoundError, 404, "NOT_FOUND"),
    ],
    ids=["400", "401", "404"],
)
def test_a_refusal_reaches_the_error_with_the_providers_message(
    refusal: Exception,
) -> None:
    asked, error = ask_scripted({MAIN: [refusal], FALLBACK: [refusal]})

    assert asked == [MAIN, FALLBACK]
    message = llm.error_text(refusal)
    assert str(error) == f"{MAIN}: {message} | {FALLBACK}: {message}"


def test_an_unknown_provider_reaches_the_error() -> None:
    _, error = ask_scripted({}, names=("anthropic:claude-x",))

    assert "anthropic:claude-x" in str(error)

import asyncio
import json
import logging
import time
from collections.abc import Callable, Mapping, Sequence
from typing import Any, TypedDict, TypeVar, cast

import aiohttp
import httpx
from django.conf import settings
from langchain.chat_models import init_chat_model
from langchain_core.exceptions import (
    ModelAPIError,
    ModelConnectionError,
    ModelError,
    ModelRateLimitError,
    ModelTimeoutError,
)
from langchain_core.language_models import BaseChatModel, LanguageModelInput
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable
from pydantic import BaseModel, ValidationError

from news_podcast.api.core.config import (
    MAX_OUTPUT_TOKENS,
    TEXT_RETRY_MINUTES,
    THINKING_LEVEL,
)
from news_podcast.api.core.gemini import (
    MAX_ATTEMPTS,
    MAX_RETRY_DELAY_SECONDS,
    RATE_LIMIT_WAIT_SECONDS,
    RETRYABLE_STATUS,
    backoff_seconds,
    is_daily_quota,
    retry_delay,
)
from news_podcast.api.core.schemas import Usage

logger = logging.getLogger(__name__)

S = TypeVar("S", bound=BaseModel)
T = TypeVar("T")

# LangChain's provider names, and the setting that holds each one's key.
API_KEY_SETTINGS = {"google_genai": "GEMINI_API_KEY", "openai": "OPENAI_API_KEY"}
TEXT_TIMEOUT_SECONDS = 180.0


# A failed answer, like invalid JSON, can be a one-off, so each model gets a second
# try before the next one.
ANSWERS_PER_MODEL = 2


class TextError(Exception):
    """No text model answered well."""


class BadAnswerError(Exception):
    """An answer that breaks the step's rules: it is asked again."""


class ModelDownError(Exception):
    """The model doesn't answer now: it is asked again after the next wait."""


class ModelDroppedError(Exception):
    """The model is out of quota, or refused (its key, its provider, a 4xx): it is
    not asked again in this run."""


class RawAnswer(TypedDict):
    """What include_raw returns. Its parsed value is left out: LangChain's parser
    closes what a cut answer left open, so the raw text is read instead."""

    raw: AIMessage


ModelFactory = Callable[[str, str, str, httpx.AsyncClient], BaseChatModel]


def split_model(name: str) -> tuple[str, str]:
    """('google_genai', 'gemini-3.8-flash') for google_genai:gemini-3.8-flash and for
    the bare gemini-3.8-flash, which init_chat_model would take for google_vertexai.
    Another bare name gets no provider."""
    provider, separator, model = name.partition(":")
    if separator:
        return provider, model
    if name.startswith("gemini"):
        return "google_genai", name
    return "", name


def model_name_error(name: str) -> str | None:
    provider, model = split_model(name)
    if provider in API_KEY_SETTINGS and model.split() == [model]:
        return None
    return (
        "Write provider:model, with google_genai or openai, such as "
        "google_genai:gemini-3.8-flash or openai:gpt-4.1-mini (a bare gemini-* "
        "name means google_genai)."
    )


def chat_model(
    provider: str, model: str, api_key: str, http_client: httpx.AsyncClient
) -> BaseChatModel:
    """The retries stay ours (TextModels), so the providers' own are off."""
    if provider == "google_genai":
        # max_retries counts attempts here: 1 is a single request.
        return init_chat_model(
            model,
            model_provider=provider,
            api_key=api_key,
            timeout=TEXT_TIMEOUT_SECONDS,
            max_retries=1,
            max_tokens=MAX_OUTPUT_TOKENS,
            reasoning_effort=THINKING_LEVEL,
        )
    # It counts retries here. The client made in this run replaces the one
    # langchain-openai keeps for the whole process, which a second asyncio.run would
    # find closed.
    return init_chat_model(
        model,
        model_provider=provider,
        api_key=api_key,
        timeout=TEXT_TIMEOUT_SECONDS,
        max_retries=0,
        http_async_client=http_client,
    )


def structured_model(
    model: BaseChatModel, schema: type[BaseModel]
) -> Runnable[LanguageModelInput, dict[str, Any] | BaseModel]:
    """The serialization schema requires the fields that have defaults too
    (json_schema_serialization_defaults_required), so every provider writes them
    all. The method is explicit, so every provider uses the same one."""
    return model.with_structured_output(
        schema.model_json_schema(mode="serialization"),
        method="json_schema",
        include_raw=True,
    )


class TextModels:
    """The run's text models, asked in order. One per asyncio.run: the models that
    are down, the ones dropped and the waits left belong to the run."""

    def __init__(
        self,
        names: Sequence[str],
        usages: list[Usage],
        http_client: httpx.AsyncClient,
        factory: ModelFactory = chat_model,
    ) -> None:
        self.names = list(names)
        # The run's list: every answer counts, broken ones included.
        self.usages = usages
        self.http_client = http_client
        self.factory = factory
        self.models: dict[str, BaseChatModel] = {}
        self.down: set[str] = set()
        self.dropped: set[str] = set()
        self.retry_minutes = list(TEXT_RETRY_MINUTES)

    async def ask(
        self,
        prompt: ChatPromptTemplate,
        values: Mapping[str, Any],
        *,
        step: str,
        schema: type[S],
        check: Callable[[S], T],
        wait: bool = True,
    ) -> T:
        """When no model answers well and one of them is down, waits
        TEXT_RETRY_MINUTES and asks them all again; wait=False makes one round."""
        messages = prompt.format_messages(**values)
        while True:
            try:
                return await self._round(messages, step, schema, check)
            except TextError:
                # With no model down, bad answers and a used-up quota don't get
                # better with time.
                if not (wait and self.down and self.retry_minutes):
                    raise
            minutes = self.retry_minutes.pop(0)
            logger.warning(f"No text model answered; asking again in {minutes} min")
            await asyncio.sleep(minutes * 60)
            self.down.clear()

    def model(self, name: str) -> BaseChatModel:
        """The model for a saved name, built on its first use with the key from the
        settings, so a key in the environment can't take over."""
        if name not in self.models:
            if model_name_error(name):
                raise ModelDroppedError(
                    f"nome inválido; use google_genai:modelo ou openai:modelo ({name})"
                )
            provider, model = split_model(name)
            setting = API_KEY_SETTINGS[provider]
            api_key = getattr(settings, setting, None)
            if not api_key:
                raise ModelDroppedError(f"{setting} não configurada")
            try:
                self.models[name] = self.factory(
                    provider, model, api_key, self.http_client
                )
            except Exception as error:
                # Building a model makes no request, so it fails the same way every
                # time: a missing integration, a bad option.
                raise ModelDroppedError(
                    f"o modelo não pôde ser criado: {error_text(error)}"
                ) from error
        return self.models[name]

    def _available(self) -> list[str]:
        return [name for name in self.names if name not in self.down | self.dropped]

    async def _round(
        self,
        messages: list[BaseMessage],
        step: str,
        schema: type[S],
        check: Callable[[S], T],
    ) -> T:
        """One round: asks each available model up to ANSWERS_PER_MODEL times."""
        errors: list[str] = []
        attempts = [
            name for name in self._available() for _ in range(ANSWERS_PER_MODEL)
        ]
        for name in attempts:
            if name not in self._available():
                continue
            try:
                return await self._answer(name, messages, step, schema, check)
            except ModelDroppedError as error:
                self.dropped.add(name)
                logger.warning(f"{name} won't be asked again in this run: {error}")
                errors.append(f"{name}: {error}")
            except ModelDownError as error:
                self.down.add(name)
                logger.warning(f"{name} is unavailable, skipping it for now: {error}")
                errors.append(f"{name}: {error}")
            except (BadAnswerError, ValidationError) as error:
                logger.warning(f"{name} failed during {step}: {error}")
                errors.append(f"{name}: {error}")
            except Exception as error:
                # An error the sorting doesn't know, such as an odd status or an
                # unreadable error body, counts as a failed answer, so the next model
                # still gets its turn.
                logger.exception(
                    f"{name} failed during {step} with an unexpected error"
                )
                errors.append(f"{name}: {error_text(error)}")
        raise TextError(" | ".join(errors) or "Nenhum modelo de texto disponível")

    async def _answer(
        self,
        name: str,
        messages: list[BaseMessage],
        step: str,
        schema: type[S],
        check: Callable[[S], T],
    ) -> T:
        structured = structured_model(self.model(name), schema)
        answer = await self._send(name, structured, messages, step)
        raw = answer["raw"]
        self.usages.append(answer_usage(raw, step, name))
        finish_reason = str(raw.response_metadata.get("finish_reason") or "")
        if finish_reason.upper() not in ("STOP", ""):
            logger.warning(
                f"{name} ({step}) stopped before the end of its answer: {finish_reason}"
            )
        data = parsed_json(str(raw.text), name, step, finish_reason)
        return check(schema.model_validate(data))

    async def _send(
        self,
        name: str,
        structured: Runnable[LanguageModelInput, dict[str, Any] | BaseModel],
        messages: list[BaseMessage],
        step: str,
    ) -> RawAnswer:
        """Up to MAX_ATTEMPTS requests, waiting between them as the error says."""
        attempt = 1
        while True:
            logger.info(
                f"{name} ({step}): waiting for an answer (attempt {attempt} of "
                f"{MAX_ATTEMPTS}, up to {TEXT_TIMEOUT_SECONDS:.0f}s)"
            )
            started = time.monotonic()
            try:
                answer = cast(RawAnswer, await structured.ainvoke(messages))
            except Exception as error:
                delay = wait_before_next_attempt(error, attempt)
                logger.warning(
                    f"{name} ({step}): {error_text(error)}; retrying in {delay:.0f}s"
                )
                await asyncio.sleep(delay)
                attempt += 1
                continue
            logger.info(
                f"{name} ({step}): answered in {time.monotonic() - started:.0f}s"
            )
            return answer


def wait_before_next_attempt(error: Exception, attempt: int) -> float:
    """The wait before trying the same model again, or the outcome that ends its
    turn: ModelDroppedError (out of quota or refused) or ModelDownError (a timeout,
    or a passing failure after the last attempt). Any other error goes up as it is,
    and the round counts it as a failed answer."""
    status = status_code(error)
    if is_rate_limit(error) and is_out_of_quota(error):
        raise ModelDroppedError(f"sem cota: {error_text(error)}") from error
    if isinstance(error, (ModelTimeoutError, TimeoutError)):
        raise ModelDownError(f"não respondeu em {TEXT_TIMEOUT_SECONDS:.0f}s") from error
    if status == 408:
        raise ModelDownError(error_text(error)) from error
    if is_rate_limit(error):
        delay = suggested_delay(error) or RATE_LIMIT_WAIT_SECONDS * attempt
    elif status in RETRYABLE_STATUS or (
        status is None
        and isinstance(
            error, (ModelAPIError, ModelConnectionError, aiohttp.ClientError)
        )
    ):
        delay = suggested_delay(error) or backoff_seconds(attempt)
    elif (status is not None and 400 <= status < 500) or (
        status is None and isinstance(error, ModelError)
    ):
        raise ModelDroppedError(error_text(error)) from error
    else:
        raise error
    if attempt >= MAX_ATTEMPTS:
        raise ModelDownError(error_text(error)) from error
    return delay


def status_code(error: BaseException) -> int | None:
    """The HTTP status, from the error or the SDK error it was raised from."""
    for candidate in (error, error.__cause__):
        for attribute in ("status_code", "code"):
            value = getattr(candidate, attribute, None)
            if isinstance(value, int):
                return value
    return None


def is_rate_limit(error: Exception) -> bool:
    return isinstance(error, ModelRateLimitError) or status_code(error) == 429


def gemini_body(error: BaseException) -> dict[str, Any] | None:
    """The body of a Gemini error, kept in the SDK error's details: the error itself
    for a 5xx, the one it was raised from for a 4xx."""
    for candidate in (error, error.__cause__):
        details = getattr(candidate, "details", None)
        if isinstance(details, dict):
            return details
    return None


def is_out_of_quota(error: Exception) -> bool:
    body = gemini_body(error)
    if body is not None:
        return is_daily_quota(body)
    return getattr(error, "code", None) == "insufficient_quota"


def suggested_delay(error: Exception) -> float | None:
    """Gemini's retryDelay or OpenAI's Retry-After, plus a second, capped."""
    body = gemini_body(error)
    if body is not None:
        return retry_delay(body)
    headers = getattr(getattr(error, "response", None), "headers", None)
    value = headers.get("retry-after") if headers is not None else None
    try:
        seconds = float(value) if value else None
    except ValueError:
        return None
    return None if seconds is None else min(seconds + 1, MAX_RETRY_DELAY_SECONDS)


def error_text(error: BaseException) -> str:
    text = str(error).strip() or type(error).__name__
    return text[:300]


def answer_usage(raw: AIMessage, step: str, name: str) -> Usage:
    """Under the name as saved, so the cost finds its price."""
    metadata = raw.usage_metadata
    if metadata is None:
        logger.warning(f"{name} ({step}) sent no token count; counting 0")
        return Usage(step=step, model=name)
    return Usage(
        step=step,
        model=name,
        input_tokens=metadata["input_tokens"],
        output_tokens=metadata["output_tokens"],
    )


def parsed_json(text: str, name: str, step: str, finish_reason: str) -> Any:
    """The answer's JSON, read strictly. A broken one is a bad answer, and the log
    shows where it breaks."""
    if not text.strip():
        raise BadAnswerError(
            f"o modelo devolveu um texto vazio ({finish_reason or 'sem motivo'})"
        )
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        around = text[max(error.pos - 150, 0) : error.pos + 150]
        logger.warning(
            f"{name} ({step}): the JSON breaks at character {error.pos} of "
            f"{len(text)} ({error.msg}): {around!r}"
        )
        raise BadAnswerError("o modelo devolveu um JSON inválido") from error

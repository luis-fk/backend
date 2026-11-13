from typing import Any

import httpx
from langchain_core.exceptions import OutputParserException
from langchain_core.language_models import BaseChatModel, LanguageModelInput
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.outputs import ChatResult
from langchain_core.runnables import Runnable, RunnableLambda
from pydantic import BaseModel, Field, SkipValidation

from news_podcast.api.core.llm import ModelFactory


class FakeChatModel(BaseChatModel):
    """Answers, or fails, as `outcomes` says, call by call, and writes each call's
    model name in `asked`."""

    model: str
    # Kept as given, not copied, so the test sees each call.
    outcomes: SkipValidation[list[Any]]
    asked: SkipValidation[list[str]]
    usage: dict[str, int] | None = Field(
        default_factory=lambda: {
            "input_tokens": 100,
            "output_tokens": 15,
            "total_tokens": 115,
        }
    )
    finish_reason: str = "STOP"
    bound: list[dict[str, Any]] = Field(default_factory=list)
    received: list[Any] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "fake"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        raise NotImplementedError

    def with_structured_output(
        self,
        schema: dict[str, Any] | type,
        *,
        include_raw: bool = False,
        **kwargs: Any,
    ) -> Runnable[LanguageModelInput, dict[str, Any] | BaseModel]:
        self.bound.append({"schema": schema, "include_raw": include_raw, **kwargs})
        return RunnableLambda(self._never, afunc=self._answer)

    def _never(self, messages: LanguageModelInput) -> dict[str, Any]:
        raise NotImplementedError

    async def _answer(self, messages: LanguageModelInput) -> dict[str, Any]:
        self.asked.append(self.model)
        self.received.append(messages)
        if not self.outcomes:
            raise AssertionError(f"{self.model} was asked more times than expected")
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        raw = AIMessage(
            content=outcome,
            usage_metadata=self.usage,
            response_metadata={"finish_reason": self.finish_reason},
        )
        # Parsed as both integrations parse a dict schema, which closes what a cut
        # answer left open.
        try:
            parsed = JsonOutputParser().parse(outcome)
        except OutputParserException as error:
            return {"raw": raw, "parsed": None, "parsing_error": error}
        return {"raw": raw, "parsed": parsed, "parsing_error": None}


def fake_factory(
    outcomes: dict[str, list[Any]],
    asked: list[str],
    built: dict[str, FakeChatModel] | None = None,
) -> ModelFactory:
    """Builds a FakeChatModel per model, whose outcomes come from `outcomes`, keyed by
    the model's name without the provider."""

    def build(
        provider: str, model: str, api_key: str, http_client: httpx.AsyncClient
    ) -> BaseChatModel:
        fake = FakeChatModel(model=model, outcomes=outcomes[model], asked=asked)
        if built is not None:
            built[model] = fake
        return fake

    return build

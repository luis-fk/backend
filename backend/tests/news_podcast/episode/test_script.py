import asyncio
import json
from datetime import date, datetime, time
from typing import Any

import httpx
import pytest
from langchain_core.prompts import ChatPromptTemplate
from pytest_django import Settings

from news_podcast.api.core.config import LOCAL_TZ
from news_podcast.api.core.llm import TextModels
from news_podcast.api.core.schemas import Script, Turn
from news_podcast.api.core.turns import MIN_SCRIPT_TURNS
from news_podcast.api.episode import config, prompts
from news_podcast.api.episode.prompts import lengthening_template, script_template
from news_podcast.api.episode.run import episode_settings
from news_podcast.api.episode.schemas import EpisodeOptions
from news_podcast.api.episode.script import (
    lengthening_values,
    script_values,
    write_script,
)
from news_podcast.models import PodcastSettings
from tests.news_podcast.fake_models import FakeChatModel, fake_factory

TURNS = [Turn(speaker="Bia", text="Bom dia")]
DEFAULT_OPTIONS = EpisodeOptions(12, 18, 1.0)
MAIN = config.TEXT_MODEL
FALLBACK = config.TEXT_FALLBACK_MODEL


def system_message(template: ChatPromptTemplate, values: dict[str, Any]) -> str:
    return str(template.format_messages(**values)[0].content)


def every_placeholder(fields: tuple[str, ...]) -> str:
    return " ".join(f"{{{field}}}" for field in fields)


def script_text(words_per_turn: int) -> str:
    turn = {"speaker": "Bia", "text": " ".join(["palavra"] * words_per_turn)}
    return json.dumps({"turns": [{**turn, "headline": False}] * MIN_SCRIPT_TURNS})


def record_waits(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    waits: list[float] = []

    async def record(seconds: float) -> None:
        waits.append(seconds)

    monkeypatch.setattr(asyncio, "sleep", record)
    return waits


def test_the_script_prompt_follows_the_configured_options() -> None:
    options = EpisodeOptions(20, 30, 1.0)
    start = datetime(2026, 11, 6, 20, 0, tzinfo=LOCAL_TZ)
    end = datetime(2026, 11, 7, 20, 0, tzinfo=LOCAL_TZ)

    script = system_message(
        script_template(prompts.SCRIPT_PROMPT),
        {
            "briefs": "",
            **script_values(options, date(2026, 11, 7), start, end, time(21, 0)),
        },
    )

    assert 'chamado "Resumo das 21"' in script
    assert "É o episódio das 21h de sábado, 7 de novembro" in script
    assert "uma fala curta com boa noite e a data" in script
    assert "entre 3400 e 5100 palavras" in script


def test_the_default_script_prompt_keeps_the_morning_episode() -> None:
    start = datetime(2026, 11, 5, 6, 0, tzinfo=LOCAL_TZ)
    end = datetime(2026, 11, 6, 6, 0, tzinfo=LOCAL_TZ)

    script = system_message(
        script_template(prompts.SCRIPT_PROMPT),
        {
            "briefs": "",
            **script_values(DEFAULT_OPTIONS, date(2026, 11, 6), start, end, time(7, 0)),
        },
    )

    assert 'chamado "Resumo das 7"' in script
    assert "É o episódio das 7h de sexta-feira, 6 de novembro" in script
    assert "uma fala curta com bom dia e a data" in script
    assert "entre 2040 e 3060 palavras" in script


def test_default_prompts_leave_the_answer_format_to_the_schema() -> None:
    for prompt in (
        prompts.SELECTION_PROMPT,
        prompts.SCRIPT_PROMPT,
        prompts.EXPAND_PROMPT,
    ):
        assert "JSON" not in prompt
        assert '"' + "item_ids" not in prompt


def test_the_script_steps_fill_every_placeholder_the_admin_accepts() -> None:
    # A placeholder left without a value would raise KeyError.
    start = datetime(2026, 11, 6, 6, 0, tzinfo=LOCAL_TZ)
    end = datetime(2026, 11, 7, 6, 0, tzinfo=LOCAL_TZ)
    values = {
        "briefs": "",
        **script_values(DEFAULT_OPTIONS, date(2026, 11, 7), start, end, time(7, 0)),
        **lengthening_values(DEFAULT_OPTIONS, Script(turns=TURNS)),
    }

    system, human = lengthening_template(
        every_placeholder(prompts.SCRIPT_FIELDS),
        every_placeholder(prompts.EXPAND_FIELDS),
    ).format_messages(**values)

    assert str(system.content).startswith(
        "Resumo das 7 Bia Léo 7h bom dia sábado, 7 de novembro "
    )
    assert human.content == f"\n\n2 2040 3060 {Script(turns=TURNS).model_dump_json()}"


def test_the_lengthening_keeps_the_script_prompt_and_adds_the_expand_prompt() -> None:
    template = lengthening_template(
        "Roteiro de {min_words} a {max_words} palavras.",
        "Tem {words}; escreva {{mais}}: {script}",
    )
    values = {
        "briefs": 'HISTÓRIA 1: Ministro diz "{x}"',
        **script_values(
            DEFAULT_OPTIONS,
            date(2026, 11, 7),
            datetime(2026, 11, 6, 6, 0, tzinfo=LOCAL_TZ),
            datetime(2026, 11, 7, 6, 0, tzinfo=LOCAL_TZ),
            time(7, 0),
        ),
        **lengthening_values(DEFAULT_OPTIONS, Script(turns=TURNS)),
    }

    system, human = template.format_messages(**values)

    assert system.content == "Roteiro de 2040 a 3060 palavras."
    assert human.content == (
        'HISTÓRIA 1: Ministro diz "{x}"\n\n'
        f"Tem 2; escreva {{mais}}: {Script(turns=TURNS).model_dump_json()}"
    )


def write_with(
    outcomes: dict[str, list[Any]], built: dict[str, FakeChatModel] | None = None
) -> Script:
    start = datetime(2026, 11, 9, 6, 0, tzinfo=LOCAL_TZ)

    async def scenario() -> Script:
        async with httpx.AsyncClient() as client:
            text = TextModels(
                [MAIN, FALLBACK], [], client, fake_factory(outcomes, [], built)
            )
            snapshot = episode_settings(PodcastSettings())
            return await write_script(
                text, snapshot, [], start.date(), start, start, time(7, 0)
            )

    return asyncio.run(scenario())


def test_lengthening_the_script_does_not_wait_for_the_models(
    monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    settings.GEMINI_API_KEY = "test-key"
    waits = record_waits(monkeypatch)

    script = write_with(
        {MAIN: [TimeoutError()], FALLBACK: [script_text(1), TimeoutError()]}
    )

    assert len(script.turns) == MIN_SCRIPT_TURNS
    assert waits == []


@pytest.mark.parametrize(
    ("lengthened_words", "kept_words"), [(5, 5), (1, 2)], ids=["longer", "shorter"]
)
def test_the_lengthened_script_is_kept_only_when_it_has_more_words(
    settings: Settings, lengthened_words: int, kept_words: int
) -> None:
    settings.GEMINI_API_KEY = "test-key"
    built: dict[str, FakeChatModel] = {}

    script = write_with(
        {MAIN: [script_text(2), script_text(lengthened_words)], FALLBACK: []}, built
    )

    assert len(script.turns[0].text.split()) == kept_words
    short, lengthening = built[MAIN].received
    assert lengthening[0].content == short[0].content
    assert str(lengthening[1].content).startswith(f"{short[1].content}\n\n")

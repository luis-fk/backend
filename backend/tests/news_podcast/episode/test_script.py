from datetime import date, datetime, time

from news_podcast.api.core.config import LOCAL_TZ
from news_podcast.api.core.schemas import Script, Turn
from news_podcast.api.episode import prompts
from news_podcast.api.episode.schemas import EpisodeOptions
from news_podcast.api.episode.script import expand_prompt, script_prompt
from news_podcast.api.episode.selection import selection_prompt

TURNS = [Turn(speaker="Bia", text="Bom dia")]
DEFAULT_OPTIONS = EpisodeOptions(12, 18, 1.0)


def test_prompts_follow_the_configured_options() -> None:
    options = EpisodeOptions(20, 30, 1.0)
    start = datetime(2026, 11, 6, 20, 0, tzinfo=LOCAL_TZ)
    end = datetime(2026, 11, 7, 20, 0, tzinfo=LOCAL_TZ)

    selection = selection_prompt(prompts.SELECTION_PROMPT, options, start, end)
    script = script_prompt(
        prompts.SCRIPT_PROMPT, options, date(2026, 11, 7), start, end, time(21, 0)
    )

    assert "em 20 a 30 minutos" in selection
    assert "Escolha de 13 a 20 histórias" in selection
    assert 'chamado "Resumo das 21"' in script
    assert "É o episódio das 21h de sábado, 7 de novembro" in script
    assert "uma fala curta com boa noite e a data" in script
    assert "entre 3400 e 5100 palavras" in script


def test_default_prompts_keep_the_morning_episode() -> None:
    start = datetime(2026, 11, 5, 6, 0, tzinfo=LOCAL_TZ)
    end = datetime(2026, 11, 6, 6, 0, tzinfo=LOCAL_TZ)

    selection = selection_prompt(prompts.SELECTION_PROMPT, DEFAULT_OPTIONS, start, end)
    script = script_prompt(
        prompts.SCRIPT_PROMPT,
        DEFAULT_OPTIONS,
        date(2026, 11, 6),
        start,
        end,
        time(7, 0),
    )

    assert "Escolha de 8 a 12 histórias" in selection
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


def test_the_default_selection_weighs_how_many_outlets_reported_a_fact() -> None:
    selection = " ".join(prompts.SELECTION_PROMPT.split())

    assert "quantos veículos diferentes" in selection
    assert "Conte cada veículo uma vez" in selection


def every_placeholder(fields: tuple[str, ...]) -> str:
    return " ".join(f"{{{field}}}" for field in fields)


def test_the_service_fills_every_placeholder_the_admin_accepts() -> None:
    # str.format raises KeyError for a placeholder it is not given.
    start = datetime(2026, 11, 6, 6, 0, tzinfo=LOCAL_TZ)
    end = datetime(2026, 11, 7, 6, 0, tzinfo=LOCAL_TZ)

    selection = selection_prompt(
        every_placeholder(prompts.SELECTION_FIELDS), DEFAULT_OPTIONS, start, end
    )
    script = script_prompt(
        every_placeholder(prompts.SCRIPT_FIELDS),
        DEFAULT_OPTIONS,
        date(2026, 11, 7),
        start,
        end,
        time(7, 0),
    )
    expand = expand_prompt(
        every_placeholder(prompts.EXPAND_FIELDS), DEFAULT_OPTIONS, Script(turns=TURNS)
    )

    assert selection.startswith("12 18 15 8 12 ")
    assert script.startswith("Resumo das 7 Bia Léo 7h bom dia sábado, 7 de novembro ")
    assert expand.startswith("2 2040 3060 ")

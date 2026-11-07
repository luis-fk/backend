from datetime import date

import pytest

from news_podcast.api.episode.costs import format_brl, price_for, usage_cost_usd
from news_podcast.api.episode.messages import (
    episode_caption,
    episode_details,
    long_date,
)
from news_podcast.api.episode.schemas import SourceText, StoryBrief, Usage

NOVEMBER = date(2026, 11, 6)
JANUARY = date(2027, 1, 4)
USAGES = [
    Usage(
        step="selection",
        model="gemini-3.6-flash",
        input_tokens=17_000,
        output_tokens=4_400,
    ),
    Usage(
        step="script",
        model="gemini-3.6-flash",
        input_tokens=20_000,
        output_tokens=9_000,
    ),
    Usage(
        step="voice",
        model="gemini-3.8-flash-lite-tts",
        input_tokens=3_500,
        output_tokens=18_300,
    ),
]


def test_prices_double_in_january_2027() -> None:
    november = price_for("gemini-3.8-flash-tts", NOVEMBER)
    january = price_for("gemini-3.8-flash-tts", JANUARY)

    assert november is not None and january is not None
    assert january.output_per_million == 2 * november.output_per_million


def test_voice_cost_follows_audio_tokens() -> None:
    eighteen_minutes = Usage(
        step="voice",
        model="gemini-3.8-flash-tts",
        input_tokens=0,
        output_tokens=18 * 60 * 25,
    )

    assert usage_cost_usd(eighteen_minutes, NOVEMBER) == pytest.approx(0.243)


def test_unknown_models_cost_nothing() -> None:
    assert (
        usage_cost_usd(Usage(step="voice", model="x", output_tokens=10), NOVEMBER) == 0
    )


def test_brazilian_number_formats() -> None:
    assert format_brl(1234.5) == "R$ 1.234,50"
    assert format_brl(0.004) == "menos de R$ 0,01"
    assert long_date(NOVEMBER) == "sexta-feira, 6 de novembro"


def test_caption_is_only_the_title_and_the_date() -> None:
    assert episode_caption("Resumo das 7", NOVEMBER) == (
        "🎙️ <b>Resumo das 7 · sexta-feira, 6 de novembro</b>"
    )


def test_details_show_the_sources_and_a_short_cost_summary() -> None:
    briefs = [
        StoryBrief(
            title=f"História {index}",
            category="politica",
            minutes=1.5,
            angle="",
            sources=[
                SourceText(outlet=outlet, title="t", text="x")
                for outlet in ("g1", "CNN Brasil")
            ],
        )
        for index in range(3)
    ]

    details = episode_details(day=NOVEMBER, briefs=briefs, usages=USAGES, plan="free")

    assert details.splitlines() == [
        "<b>Fontes:</b> CNN Brasil (3), g1 (3)",
        "",
        "💰 <b>Custo:</b> R$ 0 no plano grátis (no pago: R$ 1,04 hoje, ~R$ 31/mês)",
        "Leitura R$ 0,16 · Roteiro R$ 0,27 · Voz R$ 0,61",
    ]


def test_paid_plan_shows_the_real_cost() -> None:
    details = episode_details(day=NOVEMBER, briefs=[], usages=USAGES, plan="paid")

    assert details.splitlines()[2] == "💰 <b>Custo:</b> R$ 1,04 hoje (~R$ 31/mês)"

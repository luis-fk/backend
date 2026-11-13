from datetime import date

import pytest

from news_podcast.api.core.costs import (
    format_brl,
    usage_cost_usd,
)
from news_podcast.api.core.messages import (
    failure_message,
    long_date,
)
from news_podcast.api.core.schemas import (
    ModelPrice,
    Usage,
)

NOVEMBER = date(2026, 11, 6)
PRICES = {
    "gemini-3.6-flash": ModelPrice(0.75, 3.75),
    "gemini-3.8-flash-lite-tts": ModelPrice(0.50, 6.00),
}
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


def test_voice_cost_follows_audio_tokens() -> None:
    eighteen_minutes = Usage(
        step="voice",
        model="gemini-3.8-flash-lite-tts",
        input_tokens=0,
        output_tokens=18 * 60 * 25,
    )

    assert usage_cost_usd(eighteen_minutes, PRICES) == pytest.approx(0.162)


def test_unknown_models_cost_nothing() -> None:
    assert usage_cost_usd(Usage(step="voice", model="x", output_tokens=10), PRICES) == 0


def test_brazilian_number_formats() -> None:
    assert format_brl(1234.5) == "R$ 1.234,50"
    assert format_brl(0.004) == "menos de R$ 0,01"
    assert long_date(NOVEMBER) == "sexta-feira, 6 de novembro"


@pytest.mark.parametrize(
    ("subject", "first_line"),
    [
        ("o episódio de hoje", "⚠️ Não consegui gerar o episódio de hoje."),
        ("a aula de hoje", "⚠️ Não consegui gerar a aula de hoje."),
    ],
)
def test_a_failure_notice_names_what_failed(subject: str, first_line: str) -> None:
    message = failure_message(subject, "voz", RuntimeError("a cota <acabou>"))

    assert message.split("\n") == [
        first_line,
        "<b>Etapa:</b> voz",
        "<b>Erro:</b> a cota &lt;acabou&gt;",
        "O log completo fica no Railway.",
    ]

from datetime import date

from news_podcast.api.core.schemas import ModelPrice, Usage
from news_podcast.api.episode.messages import episode_caption, episode_details
from news_podcast.api.episode.schemas import SourceText, StoryBrief

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

    details = episode_details(briefs=briefs, usages=USAGES, prices=PRICES)

    assert details.splitlines() == [
        "<b>Fontes:</b> CNN Brasil (3), g1 (3)",
        "",
        "💰 <b>Custo no plano pago:</b> R$ 1,04 hoje (~R$ 31/mês)",
        "Leitura R$ 0,16 · Roteiro R$ 0,27 · Voz R$ 0,61",
    ]

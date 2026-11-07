import html
from collections import Counter
from collections.abc import Sequence
from datetime import date

from news_podcast.api.episode.config import BRL_PER_USD
from news_podcast.api.episode.costs import (
    format_brl,
    format_brl_rounded,
    total_cost_usd,
)
from news_podcast.api.episode.schemas import GeminiPlan, StoryBrief, Usage

WEEKDAYS = (
    "segunda-feira",
    "terça-feira",
    "quarta-feira",
    "quinta-feira",
    "sexta-feira",
    "sábado",
    "domingo",
)
MONTHS = (
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
)
DAYS_PER_MONTH = 30
MICROSOFT_LABEL = "Microsoft"
COST_STEPS = (("Leitura", "selection"), ("Roteiro", "script"), ("Voz", "voice"))


def long_date(day: date) -> str:
    return f"{WEEKDAYS[day.weekday()]}, {day.day} de {MONTHS[day.month - 1]}"


def outlet_counts(briefs: Sequence[StoryBrief]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for brief in briefs:
        outlets = {source.outlet for source in brief.sources}
        outlets.update(headline.outlet for headline in brief.other_headlines)
        counts.update(outlets)
    return counts


def sources_line(counts: Counter[str]) -> str:
    ranked = sorted(counts.items(), key=lambda pair: (-pair[1], pair[0].casefold()))
    return ", ".join(f"{outlet} ({count})" for outlet, count in ranked)


def episode_caption(podcast_name: str, day: date) -> str:
    return f"🎙️ <b>{podcast_name} · {long_date(day)}</b>"


def episode_details(
    *,
    day: date,
    briefs: Sequence[StoryBrief],
    usages: Sequence[Usage],
    plan: GeminiPlan,
) -> str:
    lines = [
        f"<b>Fontes:</b> {html.escape(sources_line(outlet_counts(briefs)))}",
        "",
        *cost_lines(day=day, usages=usages, plan=plan),
    ]
    return "\n".join(lines)


def cost_lines(*, day: date, usages: Sequence[Usage], plan: GeminiPlan) -> list[str]:
    total = total_cost_usd(usages, day)
    monthly = format_brl_rounded(total * DAYS_PER_MONTH * BRL_PER_USD)
    summary = (
        f"R$ 0 no plano grátis (no pago: {brl(total)} hoje, ~{monthly}/mês)"
        if plan == "free"
        else f"{brl(total)} hoje (~{monthly}/mês)"
    )
    steps = " · ".join(
        f"{label} {step_cost(usages, step, day)}" for label, step in COST_STEPS
    )
    return [f"💰 <b>Custo:</b> {summary}", steps]


def step_cost(usages: Sequence[Usage], step: str, day: date) -> str:
    return brl(total_cost_usd((usage for usage in usages if usage.step == step), day))


def brl(usd: float) -> str:
    return format_brl(usd * BRL_PER_USD)


def failure_message(step: str, error: Exception) -> str:
    return (
        "⚠️ Não consegui gerar o episódio de hoje.\n"
        f"<b>Etapa:</b> {html.escape(step)}\n"
        f"<b>Erro:</b> {html.escape(str(error)[:600])}\n"
        "O log completo fica no GitHub Actions."
    )

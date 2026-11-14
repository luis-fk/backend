import html
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import date, datetime

from news_podcast.api.core.config import BRL_PER_USD, LOCAL_TZ
from news_podcast.api.core.costs import format_brl_rounded, total_cost_usd
from news_podcast.api.core.messages import brl, long_date
from news_podcast.api.core.schemas import ModelPrice, Usage
from news_podcast.api.episode.schemas import StoryBrief

FAILURE_SUBJECT = "o episódio de hoje"
DAYS_PER_MONTH = 30
COST_STEPS = (("Leitura", "selection"), ("Roteiro", "script"), ("Voz", "voice"))


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
    briefs: Sequence[StoryBrief],
    usages: Sequence[Usage],
    prices: Mapping[str, ModelPrice],
) -> str:
    lines = [
        f"<b>Fontes:</b> {html.escape(sources_line(outlet_counts(briefs)))}",
        "",
        *cost_lines(usages=usages, prices=prices),
    ]
    return "\n".join(lines)


def cost_lines(
    *, usages: Sequence[Usage], prices: Mapping[str, ModelPrice]
) -> list[str]:
    total = total_cost_usd(usages, prices)
    monthly = format_brl_rounded(total * DAYS_PER_MONTH * BRL_PER_USD)
    summary = f"{brl(total)} hoje (~{monthly}/mês)"
    steps = " · ".join(
        f"{label} {step_cost(usages, step, prices)}" for label, step in COST_STEPS
    )
    return [f"💰 <b>Custo no plano pago:</b> {summary}", steps]


def step_cost(
    usages: Sequence[Usage], step: str, prices: Mapping[str, ModelPrice]
) -> str:
    in_step = (usage for usage in usages if usage.step == step)
    return brl(total_cost_usd(in_step, prices))


def local_label(moment: datetime) -> str:
    return moment.astimezone(LOCAL_TZ).strftime("%d/%m às %H:%M")

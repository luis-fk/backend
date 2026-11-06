from collections.abc import Iterable
from datetime import date

from news_podcast.api.episode.config import PRICE_CHANGE_DAY, PRICES
from news_podcast.api.episode.schemas import ModelPrice, Usage

TOKENS_PER_MILLION = 1_000_000


def price_for(model: str, day: date) -> ModelPrice | None:
    prices = PRICES.get(model)
    if prices is None:
        return None
    return prices[1] if day >= PRICE_CHANGE_DAY else prices[0]


def usage_cost_usd(usage: Usage, day: date) -> float:
    price = price_for(usage.model, day)
    if price is None:
        return 0.0
    return (
        usage.input_tokens * price.input_per_million
        + usage.output_tokens * price.output_per_million
    ) / TOKENS_PER_MILLION


def total_cost_usd(usages: Iterable[Usage], day: date) -> float:
    return sum(usage_cost_usd(usage, day) for usage in usages)


def format_brl(value: float) -> str:
    if 0 < value < 0.01:
        return "menos de R$ 0,01"
    formatted = f"{value:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"R$ {formatted}"


def format_brl_rounded(value: float) -> str:
    return format_brl(float(round(value)))[:-3]

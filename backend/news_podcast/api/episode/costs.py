from collections.abc import Iterable, Mapping

from news_podcast.api.episode.schemas import ModelPrice, Usage

TOKENS_PER_MILLION = 1_000_000


def usage_cost_usd(usage: Usage, prices: Mapping[str, ModelPrice]) -> float:
    price = prices.get(usage.model)
    if price is None:
        return 0.0
    return (
        usage.input_tokens * price.input_per_million
        + usage.output_tokens * price.output_per_million
    ) / TOKENS_PER_MILLION


def total_cost_usd(usages: Iterable[Usage], prices: Mapping[str, ModelPrice]) -> float:
    return sum(usage_cost_usd(usage, prices) for usage in usages)


def format_brl(value: float) -> str:
    if 0 < value < 0.01:
        return "menos de R$ 0,01"
    formatted = f"{value:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"R$ {formatted}"


def format_brl_rounded(value: float) -> str:
    return format_brl(float(round(value)))[:-3]

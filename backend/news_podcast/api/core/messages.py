import html
from collections.abc import Sequence
from datetime import date

from news_podcast.api.core.config import BRL_PER_USD
from news_podcast.api.core.costs import format_brl
from news_podcast.api.core.schemas import TelegramChat

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


def long_date(day: date) -> str:
    return f"{WEEKDAYS[day.weekday()]}, {day.day} de {MONTHS[day.month - 1]}"


def brl(usd: float) -> str:
    return format_brl(usd * BRL_PER_USD)


def failure_message(subject: str, step: str, error: Exception) -> str:
    return (
        f"⚠️ Não consegui gerar {subject}.\n"
        f"<b>Etapa:</b> {html.escape(step)}\n"
        f"<b>Erro:</b> {html.escape(str(error)[:600])}\n"
        "O log completo fica no Railway."
    )


def chat_list_message(chats: Sequence[TelegramChat]) -> str:
    lines = [
        f"{'👥' if chat.is_group else '👤'} {html.escape(chat.name)}: "
        f"<code>{chat.id}</code>"
        for chat in chats
    ]
    return "\n".join(
        [
            "Conversas que o bot viu nas últimas 24 horas:",
            *lines,
            "",
            "Para o resumo ir para outra conversa, troque a variável "
            "<b>TELEGRAM_CHAT_ID</b> do podcast no Railway pelo número dela.",
        ]
    )


def chat_id_message(chat_id: str) -> str:
    return (
        "Achei esta conversa! Para o resumo chegar aqui, salve este número na "
        "variável <b>TELEGRAM_CHAT_ID</b> do podcast no Railway:\n"
        f"<code>{chat_id}</code>"
    )

from typing import Any

from political_culture.api.messages.serializers import ChatHistorySerializer
from political_culture.models import ChatHistory

LANGUAGES = ("pt-BR", "en")
DEFAULT_LANGUAGE = "pt-BR"

HELP_COMMAND = "/help"

HELP_TEXTS = {
    "pt-BR": (
        "Posso ajudar com textos políticos de três jeitos:\n\n"
        "- **Analisar um texto:** cole aqui um texto de vários parágrafos, como um "
        "artigo, um discurso ou um trecho de livro. Eu o comparo com os textos da "
        "biblioteca que você marcou na página Textos, nas palavras e nos trechos "
        "mais parecidos, e aponto as ideologias de que ele mais se aproxima.\n"
        "- **Conversar sobre a biblioteca:** pergunte sobre os textos que você "
        "marcou. Posso resumir um texto, traduzir o resumo dele, procurar um trecho "
        "ou comparar textos.\n"
        "- **Voltar a um texto que você colou:** pergunte sobre um texto que você "
        "já mandou aqui.\n\n"
        "Respondo na língua em que você escrever. Um texto da biblioteca só entra "
        "nas análises depois de marcado na página Textos."
    ),
    "en": (
        "I can help with political texts in three ways:\n\n"
        "- **Analyze a text:** paste a text of several paragraphs here, such as an "
        "article, a speech or a book excerpt. I compare it with the library texts "
        "you ticked on the Texts page, in their words and closest passages, and "
        "point out the ideologies it comes closest to.\n"
        "- **Talk about the library:** ask about the texts you ticked. I can "
        "summarize a text, translate its summary, find a passage or compare texts.\n"
        "- **Go back to a text you pasted:** ask about a text you already sent "
        "here.\n\n"
        "I answer in the language you write in. A library text only counts in the "
        "analyses once you tick it on the Texts page."
    ),
}


def is_help(text: str) -> bool:
    return text.strip().lower() == HELP_COMMAND


def answer_help(text: str, user_id: int, language: str) -> dict[str, Any]:
    ChatHistory.objects.create(user_id=user_id, role="human", message=text.strip())
    answer = ChatHistory.objects.create(
        user_id=user_id, role="ai", message=HELP_TEXTS[language]
    )
    return ChatHistorySerializer(answer).data

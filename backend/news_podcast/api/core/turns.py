import re
import unicodedata
from collections.abc import Sequence

from news_podcast.api.core.schemas import Host, Turn

URL_PATTERN = re.compile(r"https?://\S+")
MARKDOWN_PATTERN = re.compile(r"[*_#`\[\]]")
EMOJI_PATTERN = re.compile("[\U0001f000-\U0001faff☀-➿️]")
SPACE_PATTERN = re.compile(r"\s+")
SENTENCE_END_PATTERN = re.compile(r"(?<=[.!?…])\s+")


# A script with fewer turns isn't a real episode.
MIN_SCRIPT_TURNS = 10


def ascii_fold(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return normalized.encode("ascii", "ignore").decode().casefold().strip()


def clean_spoken_text(text: str) -> str:
    without_links = URL_PATTERN.sub("", text)
    without_markup = MARKDOWN_PATTERN.sub("", without_links)
    without_emoji = EMOJI_PATTERN.sub("", without_markup)
    return SPACE_PATTERN.sub(" ", without_emoji).strip()


def clean_turns(turns: Sequence[Turn], hosts: Sequence[Host]) -> list[Turn]:
    names = {ascii_fold(host.name): host.name for host in hosts}
    names.update({ascii_fold(host.speaker_id): host.name for host in hosts})

    cleaned: list[Turn] = []
    for turn in turns:
        text = clean_spoken_text(_without_speaker_prefix(turn.text, names))
        if not text:
            continue
        fallback_speaker = hosts[len(cleaned) % len(hosts)].name
        speaker = names.get(ascii_fold(turn.speaker), fallback_speaker)
        cleaned.append(turn.model_copy(update={"speaker": speaker, "text": text}))
    return cleaned


def _without_speaker_prefix(text: str, names: dict[str, str]) -> str:
    head, separator, tail = text.partition(":")
    if separator and ascii_fold(head.strip(" *")) in names:
        return tail
    return text


def count_words(turns: Sequence[Turn]) -> int:
    return sum(len(turn.text.split()) for turn in turns)


def chunk_turns(turns: Sequence[Turn], max_words: int) -> list[list[Turn]]:
    chunks: list[list[Turn]] = []
    current: list[Turn] = []
    current_words = 0

    for turn in _split_long_turns(turns, max_words):
        words = len(turn.text.split())
        if current and current_words + words > max_words:
            chunks.append(current)
            current, current_words = [], 0
        current.append(turn)
        current_words += words

    if current:
        chunks.append(current)
    return chunks


def _split_long_turns(turns: Sequence[Turn], max_words: int) -> list[Turn]:
    pieces: list[Turn] = []
    for turn in turns:
        if len(turn.text.split()) <= max_words:
            pieces.append(turn)
            continue

        buffer: list[str] = []
        for sentence in SENTENCE_END_PATTERN.split(turn.text):
            if buffer and len(" ".join([*buffer, sentence]).split()) > max_words:
                pieces.append(turn.model_copy(update={"text": " ".join(buffer)}))
                buffer = []
            buffer.append(sentence)
        if buffer:
            pieces.append(turn.model_copy(update={"text": " ".join(buffer)}))
    return pieces

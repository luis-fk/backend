from collections.abc import Sequence
from datetime import date, datetime, time
from typing import Any

from news_podcast.api.core.config import HOSTS
from news_podcast.api.core.gemini import GeminiError
from news_podcast.api.core.messages import long_date
from news_podcast.api.core.schemas import Script
from news_podcast.api.core.turns import MIN_SCRIPT_TURNS, clean_turns, count_words
from news_podcast.api.episode.messages import local_label
from news_podcast.api.episode.options import (
    greeting,
    podcast_name,
    spoken_time,
    word_range,
)
from news_podcast.api.episode.schemas import EpisodeOptions, StoryBrief


def parse_script(data: Any) -> Script:
    script = Script.model_validate(data)
    turns = clean_turns(script.turns, HOSTS)
    if len(turns) < MIN_SCRIPT_TURNS:
        raise GeminiError(f"o roteiro veio com só {len(turns)} falas")
    return script.model_copy(update={"turns": turns})


def script_prompt(
    template: str,
    options: EpisodeOptions,
    day: date,
    start: datetime,
    end: datetime,
    send_at: time,
) -> str:
    min_words, max_words = word_range(options)
    return template.format(
        podcast_name=podcast_name(send_at),
        host_a=HOSTS[0].name,
        host_b=HOSTS[1].name,
        send_time=spoken_time(send_at),
        greeting=greeting(send_at),
        today=long_date(day),
        window_start=local_label(start),
        window_end=local_label(end),
        min_words=min_words,
        max_words=max_words,
    )


def expand_prompt(template: str, options: EpisodeOptions, script: Script) -> str:
    min_words, max_words = word_range(options)
    return template.format(
        words=count_words(script.turns),
        min_words=min_words,
        max_words=max_words,
        script=script.model_dump_json(),
    )


def format_briefs(briefs: Sequence[StoryBrief], words_per_minute: int) -> str:
    blocks: list[str] = []
    for index, brief in enumerate(briefs, start=1):
        lines = [
            f"HISTÓRIA {index}: {brief.title}",
            f"Categoria: {brief.category} · tamanho: cerca de "
            f"{round(brief.minutes * words_per_minute)} palavras",
        ]
        if brief.angle:
            lines.append(f"Foco: {brief.angle}")
        for source in brief.sources:
            lines.append(f"\nFonte: {source.outlet} — {source.title}\n{source.text}")
        if brief.other_headlines:
            lines.append("\nOutros veículos que também noticiaram:")
            lines.extend(
                f"- {headline.outlet}: {headline.title}. {headline.text}".strip()
                for headline in brief.other_headlines
            )
        blocks.append("\n".join(lines))
    return "\n\n---\n\n".join(blocks)

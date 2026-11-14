import logging
from collections.abc import Sequence
from datetime import date, datetime, time
from typing import Any

from news_podcast.api.core.config import HOSTS
from news_podcast.api.core.llm import TextError, TextModels
from news_podcast.api.core.messages import long_date
from news_podcast.api.core.schemas import Script
from news_podcast.api.core.turns import checked_turns, count_words
from news_podcast.api.episode.config import SHORT_SCRIPT_RATIO
from news_podcast.api.episode.messages import local_label
from news_podcast.api.episode.options import (
    greeting,
    podcast_name,
    spoken_time,
    word_range,
    words_per_minute,
)
from news_podcast.api.episode.prompts import lengthening_template, script_template
from news_podcast.api.episode.schemas import EpisodeOptions, EpisodeSettings, StoryBrief

logger = logging.getLogger(__name__)


async def write_script(
    text: TextModels,
    settings: EpisodeSettings,
    briefs: Sequence[StoryBrief],
    day: date,
    start: datetime,
    end: datetime,
    send_at: time,
) -> Script:
    options = settings.options
    min_words, _ = word_range(options)
    values = {
        "briefs": format_briefs(briefs, words_per_minute(options)),
        **script_values(options, day, start, end, send_at),
    }
    script = await text.ask(
        script_template(settings.script_prompt),
        values,
        step="script",
        schema=Script,
        check=checked_script,
    )

    words = count_words(script.turns)
    logger.info(f"Script has {words} words in {len(script.turns)} turns")
    if words >= SHORT_SCRIPT_RATIO * min_words:
        return script

    try:
        # One round and no wait: the short script will do.
        longer = await text.ask(
            lengthening_template(settings.script_prompt, settings.expand_prompt),
            {**values, **lengthening_values(options, script)},
            step="script",
            schema=Script,
            check=checked_script,
            wait=False,
        )
    except TextError as error:
        logger.warning(f"Could not lengthen the script: {error}")
        return script

    logger.info(f"Lengthened script has {count_words(longer.turns)} words")
    return longer if count_words(longer.turns) > words else script


def checked_script(script: Script) -> Script:
    return script.model_copy(update={"turns": checked_turns(script.turns, HOSTS)})


def script_values(
    options: EpisodeOptions,
    day: date,
    start: datetime,
    end: datetime,
    send_at: time,
) -> dict[str, Any]:
    """The values of the script prompt's placeholders (SCRIPT_FIELDS)."""
    min_words, max_words = word_range(options)
    return {
        "podcast_name": podcast_name(send_at),
        "host_a": HOSTS[0].name,
        "host_b": HOSTS[1].name,
        "send_time": spoken_time(send_at),
        "greeting": greeting(send_at),
        "today": long_date(day),
        "window_start": local_label(start),
        "window_end": local_label(end),
        "min_words": min_words,
        "max_words": max_words,
    }


def lengthening_values(options: EpisodeOptions, script: Script) -> dict[str, Any]:
    """The values of the expand prompt's placeholders (EXPAND_FIELDS)."""
    min_words, max_words = word_range(options)
    return {
        "words": count_words(script.turns),
        "min_words": min_words,
        "max_words": max_words,
        "script": script.model_dump_json(),
    }


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

import asyncio
import logging
from pathlib import Path

from news_podcast.api.core.config import HOSTS, TTS_CHUNK_WORDS
from news_podcast.api.core.schemas import Turn, Usage
from news_podcast.api.core.turns import chunk_turns
from news_podcast.api.core.voice.base import VoiceProvider, VoiceUnavailableError

logger = logging.getLogger(__name__)


async def narrate(
    voice: VoiceProvider,
    turns: list[Turn],
    *,
    style: str,
    headline_style: str,
    workdir: Path,
    usages: list[Usage],
    waits: list[int],
    step: str = "voice",
) -> list[Path]:
    """The turns read aloud, one WAV file per chunk in workdir, which never
    overwrites a part already there. Each chunk's usage joins usages as soon as the
    chunk is done, so a run that fails later keeps its cost. waits holds the minutes
    the run may still wait for an unavailable voice, shared by all its chunks: there
    is no other voice to fall back on."""
    chunks = chunk_turns(turns, TTS_CHUNK_WORDS)
    parts: list[Path] = []
    for index, chunk in enumerate(chunks, start=1):
        logger.info(f"Voice: part {index} of {len(chunks)}")
        audio, usage = await _synthesize_patiently(
            voice,
            chunk,
            style=style,
            headline_style=headline_style,
            waits=waits,
            step=step,
        )
        usages.append(usage)
        path = workdir / f"voice_{index:03d}.wav"
        # "x" refuses an existing file: a second call in the same workdir would
        # otherwise replace the first call's parts, and the episode would repeat one.
        with path.open("xb") as part:
            part.write(audio)
        parts.append(path)
    return parts


async def _synthesize_patiently(
    voice: VoiceProvider,
    turns: list[Turn],
    *,
    style: str,
    headline_style: str,
    waits: list[int],
    step: str,
) -> tuple[bytes, Usage]:
    while True:
        try:
            return await voice.synthesize(
                turns, HOSTS, style=style, headline_style=headline_style, step=step
            )
        except VoiceUnavailableError as error:
            if not waits:
                raise
            minutes = waits.pop(0)
            logger.warning(
                f"The voice is unavailable ({error}); trying again in {minutes} min"
            )
            await asyncio.sleep(minutes * 60)

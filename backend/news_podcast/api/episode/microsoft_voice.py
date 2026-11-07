import asyncio
import logging
from collections.abc import Sequence
from pathlib import Path

import edge_tts

from news_podcast.api.episode.config import MICROSOFT_RATE
from news_podcast.api.episode.schemas import Host, Turn

logger = logging.getLogger(__name__)

MAX_PARALLEL_REQUESTS = 4
MAX_ATTEMPTS = 3


class MicrosoftVoiceError(Exception):
    pass


async def synthesize_turns(
    turns: list[Turn], hosts: Sequence[Host], workdir: Path, prefix: str = "ms"
) -> list[Path]:
    voices = {host.name: host.microsoft_voice for host in hosts}
    semaphore = asyncio.Semaphore(MAX_PARALLEL_REQUESTS)

    async def synthesize(index: int, turn: Turn) -> Path:
        path = workdir / f"{prefix}_{index:04d}.mp3"
        voice = voices.get(turn.speaker, hosts[0].microsoft_voice)
        async with semaphore:
            await save_with_retry(turn.text, voice, path)
        return path

    paths = await asyncio.gather(
        *[synthesize(index, turn) for index, turn in enumerate(turns)]
    )
    return list(paths)


async def save_with_retry(text: str, voice: str, path: Path) -> None:
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            await edge_tts.Communicate(text, voice, rate=MICROSOFT_RATE).save(str(path))
            if path.exists() and path.stat().st_size > 0:
                return
        except Exception as error:
            logger.warning(f"Microsoft voice attempt {attempt} failed: {error}")
        await asyncio.sleep(2 * attempt)

    raise MicrosoftVoiceError(
        f"A voz da Microsoft falhou {MAX_ATTEMPTS} vezes seguidas num trecho"
    )

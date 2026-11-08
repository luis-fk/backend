import asyncio
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

SAMPLE_RATE = "24000"
OPUS_BITRATE = "32k"
GAP_SECONDS = 0.25
LOUDNESS_FILTER = "loudnorm=I=-16:TP=-1.5:LRA=11"
FFMPEG = ("ffmpeg", "-hide_banner", "-loglevel", "error", "-y")


class AudioError(Exception):
    pass


async def run_tool(*args: str) -> str:
    process = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        details = stderr.decode(errors="replace").strip()[-500:]
        raise AudioError(f"{args[0]} falhou: {details}")
    return stdout.decode()


async def build_voice_note(parts: list[Path], output: Path, workdir: Path) -> float:
    if not parts:
        raise AudioError("Nenhum trecho de áudio para juntar")

    normalized = [
        await to_wav(part, workdir / f"part_{index:04d}.wav")
        for index, part in enumerate(parts)
    ]
    silence = await make_silence(workdir / "silence.wav", GAP_SECONDS)
    playlist = write_playlist(normalized, silence, workdir / "playlist.txt")

    await run_tool(
        *FFMPEG,
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(playlist),
        "-af",
        LOUDNESS_FILTER,
        "-ac",
        "1",
        "-c:a",
        "libopus",
        "-b:a",
        OPUS_BITRATE,
        "-application",
        "voip",
        str(output),
    )
    duration = await audio_duration(output)
    logger.info(f"Built {output.name} with {len(parts)} parts ({duration:.0f}s)")
    return duration


async def to_wav(source: Path, target: Path) -> Path:
    await run_tool(
        *FFMPEG,
        "-i",
        str(source),
        "-ar",
        SAMPLE_RATE,
        "-ac",
        "1",
        "-c:a",
        "pcm_s16le",
        str(target),
    )
    return target


async def make_silence(target: Path, seconds: float) -> Path:
    await run_tool(
        *FFMPEG,
        "-f",
        "lavfi",
        "-i",
        f"anullsrc=r={SAMPLE_RATE}:cl=mono",
        "-t",
        f"{seconds:.2f}",
        "-c:a",
        "pcm_s16le",
        str(target),
    )
    return target


def write_playlist(parts: list[Path], silence: Path, target: Path) -> Path:
    lines: list[str] = []
    for index, part in enumerate(parts):
        if index:
            lines.append(f"file '{silence.resolve().as_posix()}'")
        lines.append(f"file '{part.resolve().as_posix()}'")
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


async def audio_duration(path: Path) -> float:
    output = await run_tool(
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(path),
    )
    return float(output.strip())

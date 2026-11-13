import asyncio
from collections.abc import Sequence
from pathlib import Path

import pytest

from news_podcast.api.core.config import HOSTS, TTS_CHUNK_WORDS, VOICE_RETRY_MINUTES
from news_podcast.api.core.costs import total_cost_usd
from news_podcast.api.core.schemas import Host, ModelPrice, Turn, Usage
from news_podcast.api.core.turns import chunk_turns
from news_podcast.api.core.voice.base import (
    VoiceError,
    VoiceQuotaExhaustedError,
    VoiceUnavailableError,
)
from news_podcast.api.core.voice.narration import narrate

MODEL = "google_genai:gemini-3.8-flash-lite-tts"
STYLE = "Conversa calma."
HEADLINE_STYLE = "Manchetes enfáticas."
# Three turns of 400 words: each is a chunk of its own, since two pass 650 words.
LONG_SCRIPT = [
    Turn(speaker=speaker, text=" ".join([word] * 400))
    for speaker, word in [("Bia", "um"), ("Léo", "dois"), ("Bia", "três")]
]


class FakeVoice:
    """Answers each request in turn with the next outcome: None answers, an error is
    raised. Without outcomes left, it answers."""

    def __init__(
        self,
        outcomes: Sequence[Exception | None] = (),
        usages: list[Usage] | None = None,
    ) -> None:
        self.outcomes = list(outcomes)
        self.usages = usages
        self.chunks: list[list[Turn]] = []
        self.hosts: list[Sequence[Host]] = []
        self.styles: list[tuple[str, str, str]] = []
        self.usages_seen: list[int] = []

    async def synthesize(
        self,
        turns: list[Turn],
        hosts: Sequence[Host],
        *,
        style: str,
        headline_style: str,
        step: str,
    ) -> tuple[bytes, Usage]:
        self.chunks.append(turns)
        self.hosts.append(hosts)
        self.styles.append((style, headline_style, step))
        if self.usages is not None:
            self.usages_seen.append(len(self.usages))
        outcome = self.outcomes.pop(0) if self.outcomes else None
        if outcome is not None:
            raise outcome
        return (
            f"audio {len(self.chunks)}".encode(),
            Usage(step=step, model=MODEL, output_tokens=1_000),
        )


def record_waits(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    waits: list[float] = []

    async def record(seconds: float) -> None:
        waits.append(seconds)

    monkeypatch.setattr(asyncio, "sleep", record)
    return waits


def narrate_with(
    voice: FakeVoice,
    turns: list[Turn],
    workdir: Path,
    usages: list[Usage] | None = None,
    waits: list[int] | None = None,
) -> list[Path]:
    return asyncio.run(
        narrate(
            voice,
            turns,
            style=STYLE,
            headline_style=HEADLINE_STYLE,
            workdir=workdir,
            usages=[] if usages is None else usages,
            waits=list(VOICE_RETRY_MINUTES) if waits is None else waits,
        )
    )


def test_the_chunks_go_out_in_order_and_each_becomes_a_wav_part(
    tmp_path: Path,
) -> None:
    voice = FakeVoice()

    parts = narrate_with(voice, LONG_SCRIPT, tmp_path)

    assert voice.chunks == chunk_turns(LONG_SCRIPT, TTS_CHUNK_WORDS)
    assert len(voice.chunks) == 3
    assert voice.hosts == [HOSTS] * 3
    assert voice.styles == [(STYLE, HEADLINE_STYLE, "voice")] * 3
    assert parts == [tmp_path / f"voice_{index:03d}.wav" for index in (1, 2, 3)]
    assert [part.read_bytes() for part in parts] == [b"audio 1", b"audio 2", b"audio 3"]


def test_each_chunk_s_usage_is_kept_as_soon_as_it_is_done(tmp_path: Path) -> None:
    usages: list[Usage] = []
    voice = FakeVoice(usages=usages)

    narrate_with(voice, LONG_SCRIPT, tmp_path, usages=usages)

    assert voice.usages_seen == [0, 1, 2]
    assert usages == [Usage(step="voice", model=MODEL, output_tokens=1_000)] * 3


def test_the_voice_waits_and_sends_the_same_chunk_again_when_it_is_unavailable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    waits = record_waits(monkeypatch)
    remaining = list(VOICE_RETRY_MINUTES)
    voice = FakeVoice([VoiceUnavailableError("503")])

    narrate_with(voice, LONG_SCRIPT[:1], tmp_path, waits=remaining)

    assert waits == [VOICE_RETRY_MINUTES[0] * 60]
    assert remaining == list(VOICE_RETRY_MINUTES[1:])
    assert voice.chunks == [LONG_SCRIPT[:1], LONG_SCRIPT[:1]]


def test_the_voice_gives_up_after_the_last_wait(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    waits = record_waits(monkeypatch)
    failures = [VoiceUnavailableError("503")] * (len(VOICE_RETRY_MINUTES) + 1)

    with pytest.raises(VoiceUnavailableError):
        narrate_with(FakeVoice(failures), LONG_SCRIPT[:1], tmp_path)

    assert waits == [minutes * 60 for minutes in VOICE_RETRY_MINUTES]


def test_every_chunk_of_the_run_draws_on_the_same_waits(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    waits = record_waits(monkeypatch)
    usages: list[Usage] = []
    unavailable = VoiceUnavailableError("503")
    voice = FakeVoice([unavailable, None, unavailable, None, unavailable])

    with pytest.raises(VoiceUnavailableError):
        narrate_with(voice, LONG_SCRIPT, tmp_path, usages=usages)

    assert waits == [minutes * 60 for minutes in VOICE_RETRY_MINUTES]
    assert len(usages) == 2


def test_the_voice_does_not_wait_when_the_daily_quota_is_over(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    waits = record_waits(monkeypatch)
    remaining = list(VOICE_RETRY_MINUTES)

    with pytest.raises(VoiceQuotaExhaustedError):
        narrate_with(
            FakeVoice([VoiceQuotaExhaustedError("429")]),
            LONG_SCRIPT,
            tmp_path,
            waits=remaining,
        )

    assert waits == []
    assert remaining == list(VOICE_RETRY_MINUTES)


def test_a_voice_error_goes_up_without_a_wait(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    waits = record_waits(monkeypatch)

    with pytest.raises(VoiceError, match="400"):
        narrate_with(
            FakeVoice([VoiceError("Gemini respondeu 400")]), LONG_SCRIPT, tmp_path
        )

    assert waits == []


def test_a_chunk_that_fails_for_good_keeps_the_cost_of_the_ones_before(
    tmp_path: Path,
) -> None:
    usages: list[Usage] = []
    voice = FakeVoice([None, VoiceError("Gemini respondeu 400")])

    with pytest.raises(VoiceError):
        narrate_with(voice, LONG_SCRIPT, tmp_path, usages=usages)

    assert usages == [Usage(step="voice", model=MODEL, output_tokens=1_000)]
    prices = {MODEL: ModelPrice(0.50, 6.00)}
    assert total_cost_usd(usages, prices) == pytest.approx(0.006)

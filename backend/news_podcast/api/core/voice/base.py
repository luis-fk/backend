from collections.abc import Sequence
from typing import Protocol

from news_podcast.api.core.schemas import Host, Turn, Usage


class VoiceError(Exception):
    """The voice failed, and only a fix helps: a refused request, an answer with no
    audio, a missing key or a voice model with no implementation."""


class VoiceUnavailableError(VoiceError):
    """The voice doesn't answer now: a wait helps."""


class VoiceQuotaExhaustedError(VoiceError):
    """The day's voice quota is used up: no wait helps."""


class VoiceProvider(Protocol):
    """A provider's voice. voice_provider (providers.py) builds one from the voice
    model's name."""

    async def synthesize(
        self,
        turns: list[Turn],
        hosts: Sequence[Host],
        *,
        style: str,
        headline_style: str,
        step: str,
    ) -> tuple[bytes, Usage]:
        """The turns read with each host's voice, as WAV, and the request's usage."""
        ...

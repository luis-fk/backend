import asyncio
import base64
import json
from typing import Any

import httpx
import pytest

from news_podcast.api.core.config import (
    HOSTS,
)
from news_podcast.api.core.gemini import (
    MAX_ATTEMPTS,
    RATE_LIMIT_WAIT_SECONDS,
    GeminiClient,
    GeminiQuotaExhaustedError,
    GeminiUnavailableError,
    build_tts_body,
    extract_audio_wav,
    is_daily_quota,
    pcm_to_wav,
    retry_delay,
    wav_duration,
)
from news_podcast.api.core.schemas import (
    Turn,
)

ONE_SECOND_OF_SILENCE = pcm_to_wav(b"\x00\x00" * 24000)
AUDIO_ANSWER = {
    "steps": [
        {
            "type": "model_output",
            "content": [
                {
                    "type": "audio",
                    "data": base64.b64encode(ONE_SECOND_OF_SILENCE).decode(),
                }
            ],
        }
    ]
}
STYLE = "Calm conversation."
HEADLINE_STYLE = "Emphatic headlines."


def quota_error(quota_id: str) -> dict[str, Any]:
    return {
        "error": {
            "code": 429,
            "message": "Quota exceeded",
            "details": [
                {
                    "@type": "type.googleapis.com/google.rpc.QuotaFailure",
                    "violations": [{"quotaId": quota_id}],
                },
                {
                    "@type": "type.googleapis.com/google.rpc.RetryInfo",
                    "retryDelay": "7s",
                },
            ],
        }
    }


async def synthesize(client: httpx.AsyncClient) -> bytes:
    audio, _ = await GeminiClient(client, "key").synthesize_dialogue(
        "gemini-3.8-flash-lite-tts",
        [Turn(speaker="Bia", text="Oi")],
        HOSTS,
        "voice",
        style=STYLE,
        headline_style=HEADLINE_STYLE,
    )
    return audio


def record_waits(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    waits: list[float] = []

    async def record(seconds: float) -> None:
        waits.append(seconds)

    monkeypatch.setattr(asyncio, "sleep", record)
    return waits


def test_daily_quota_is_told_apart_from_per_minute_limits() -> None:
    assert is_daily_quota(quota_error("GenerateRequestsPerDayPerProjectPerModel"))
    assert not is_daily_quota(quota_error("GenerateRequestsPerMinutePerProject"))
    assert retry_delay(quota_error("x")) == 8.0


def test_tts_body_uses_one_annotated_part_per_turn() -> None:
    turns = [Turn(speaker="Bia", text="Oi"), Turn(speaker="Léo", text="Olá")]

    body = build_tts_body("gemini-3.8-flash-tts", turns, HOSTS, STYLE, HEADLINE_STYLE)

    content = body["input"][0]["content"]
    assert [part["annotations"][0]["speaker"] for part in content] == ["Bia", "Leo"]
    assert body["generation_config"]["speech_config"]["speakers"] == [
        {"speaker": "Bia", "voice": "Kore"},
        {"speaker": "Leo", "voice": "Charon"},
    ]


def test_extract_audio_reads_the_model_output_step() -> None:
    audio = extract_audio_wav(AUDIO_ANSWER)

    assert wav_duration(audio) == pytest.approx(1.0)


def test_extract_audio_wraps_raw_pcm_in_a_wav_header() -> None:
    raw = base64.b64encode(b"\x00\x00" * 12000).decode()
    response = {
        "steps": [
            {
                "type": "model_output",
                "content": [{"type": "audio", "data": raw, "mime_type": "audio/l16"}],
            }
        ]
    }

    assert wav_duration(extract_audio_wav(response)) == pytest.approx(0.5)


def test_the_voice_retries_after_a_per_minute_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    waits = record_waits(monkeypatch)
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        if len(calls) == 1:
            error = quota_error("GenerateRequestsPerMinutePerProject")
            error["error"]["details"][1]["retryDelay"] = "0s"
            return httpx.Response(429, json=error)
        return httpx.Response(200, json=AUDIO_ANSWER)

    async def scenario() -> bytes:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await synthesize(client)

    audio = asyncio.run(scenario())

    assert wav_duration(audio) == pytest.approx(1.0)
    assert len(calls) == 2
    assert waits == [1.0]


def test_daily_quota_stops_without_retrying() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["response_format"] == {"type": "audio"}
        return httpx.Response(429, json=quota_error("RequestsPerDay-FreeTier"))

    async def scenario() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await synthesize(client)

    with pytest.raises(GeminiQuotaExhaustedError):
        asyncio.run(scenario())


def test_the_voice_gives_up_after_a_few_overloaded_attempts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record_waits(monkeypatch)
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(503, json={"error": {"message": "high demand"}})

    async def scenario() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await synthesize(client)

    with pytest.raises(GeminiUnavailableError, match="503"):
        asyncio.run(scenario())
    assert len(calls) == MAX_ATTEMPTS


def test_the_voice_does_not_insist_after_a_timeout() -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        raise httpx.ReadTimeout("timed out", request=request)

    async def scenario() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await synthesize(client)

    with pytest.raises(GeminiUnavailableError, match="não respondeu"):
        asyncio.run(scenario())
    assert len(calls) == 1


def test_tts_body_reads_the_headlines_with_an_emphatic_style() -> None:
    turns = [
        Turn(speaker="Bia", text="Juros sobem de novo.", headline=True),
        Turn(speaker="Léo", text="Bom dia! Hoje é sexta-feira."),
    ]

    body = build_tts_body(
        "gemini-3.8-flash-lite-tts", turns, HOSTS, STYLE, HEADLINE_STYLE
    )

    content = body["input"][0]["content"]
    styles = [part["annotations"][0]["style"] for part in content]
    assert styles == [HEADLINE_STYLE, STYLE]


def test_rate_limit_without_a_suggested_delay_waits_half_a_minute(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    waits = record_waits(monkeypatch)
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        if len(calls) == 1:
            return httpx.Response(429, json={"error": {"message": "Rate limited"}})
        return httpx.Response(200, json=AUDIO_ANSWER)

    async def scenario() -> bytes:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await synthesize(client)

    assert wav_duration(asyncio.run(scenario())) == pytest.approx(1.0)
    assert waits == [RATE_LIMIT_WAIT_SECONDS]

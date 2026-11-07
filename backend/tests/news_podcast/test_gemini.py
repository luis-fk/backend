import asyncio
import base64
import json
from typing import Any

import httpx
import pytest

from news_podcast.api.episode.config import HEADLINE_TTS_STYLE, HOSTS, TTS_STYLE
from news_podcast.api.episode.gemini import (
    MAX_ATTEMPTS,
    RATE_LIMIT_WAIT_SECONDS,
    GeminiClient,
    GeminiQuotaExhaustedError,
    GeminiUnavailableError,
    build_tts_body,
    extract_audio_wav,
    is_daily_quota,
    parse_json_text,
    pcm_to_wav,
    retry_delay,
    wav_duration,
)
from news_podcast.api.episode.schemas import Turn

ONE_SECOND_OF_SILENCE = pcm_to_wav(b"\x00\x00" * 24000)


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


def test_parse_json_text_accepts_code_fences_and_extra_text() -> None:
    assert parse_json_text('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json_text('Aqui está: {"a": 2} pronto') == {"a": 2}


def test_daily_quota_is_told_apart_from_per_minute_limits() -> None:
    assert is_daily_quota(quota_error("GenerateRequestsPerDayPerProjectPerModel"))
    assert not is_daily_quota(quota_error("GenerateRequestsPerMinutePerProject"))
    assert retry_delay(quota_error("x")) == 8.0


def test_tts_body_uses_one_annotated_part_per_turn() -> None:
    turns = [Turn(speaker="Bia", text="Oi"), Turn(speaker="Léo", text="Olá")]

    body = build_tts_body("gemini-3.8-flash-tts", turns, HOSTS)

    content = body["input"][0]["content"]
    assert [part["annotations"][0]["speaker"] for part in content] == ["Bia", "Leo"]
    assert body["generation_config"]["speech_config"]["speakers"] == [
        {"speaker": "Bia", "voice": "Kore"},
        {"speaker": "Leo", "voice": "Charon"},
    ]


def test_extract_audio_reads_the_model_output_step() -> None:
    encoded = base64.b64encode(ONE_SECOND_OF_SILENCE).decode()
    response = {
        "steps": [
            {"type": "user_input", "content": []},
            {"type": "model_output", "content": [{"type": "audio", "data": encoded}]},
        ]
    }

    audio = extract_audio_wav(response)

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


def test_generate_json_retries_after_a_per_minute_limit() -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        if len(calls) == 1:
            error = quota_error("GenerateRequestsPerMinutePerProject")
            error["error"]["details"][1]["retryDelay"] = "0s"
            return httpx.Response(429, json=error)
        return httpx.Response(
            200,
            json={
                "candidates": [{"content": {"parts": [{"text": '{"ok": true}'}]}}],
                "usageMetadata": {
                    "promptTokenCount": 100,
                    "candidatesTokenCount": 10,
                    "thoughtsTokenCount": 5,
                },
            },
        )

    async def scenario() -> tuple[Any, int]:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            data, usage = await GeminiClient(client, "key").generate_json(
                "gemini-3.8-flash", "system", "user", "selection"
            )
            return data, usage.output_tokens

    data, output_tokens = asyncio.run(scenario())

    assert data == {"ok": True}
    assert output_tokens == 15
    assert len(calls) == 2


def test_daily_quota_stops_without_retrying() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["response_format"] == {"type": "audio"}
        return httpx.Response(429, json=quota_error("RequestsPerDay-FreeTier"))

    async def scenario() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await GeminiClient(client, "key").synthesize_dialogue(
                "gemini-3.8-flash-tts", [Turn(speaker="Bia", text="Oi")], HOSTS, "voice"
            )

    with pytest.raises(GeminiQuotaExhaustedError):
        asyncio.run(scenario())


def test_generate_json_gives_up_after_a_few_overloaded_attempts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []

    async def no_wait(seconds: float) -> None:
        return None

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(503, json={"error": {"message": "high demand"}})

    async def scenario() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await GeminiClient(client, "key").generate_json(
                "gemini-3.8-flash", "system", "user", "script"
            )

    monkeypatch.setattr(asyncio, "sleep", no_wait)
    with pytest.raises(GeminiUnavailableError, match="503"):
        asyncio.run(scenario())
    assert len(calls) == MAX_ATTEMPTS


def test_generate_json_does_not_insist_after_a_timeout() -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        raise httpx.ReadTimeout("timed out", request=request)

    async def scenario() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await GeminiClient(client, "key").generate_json(
                "gemini-3.8-flash", "system", "user", "selection"
            )

    with pytest.raises(GeminiUnavailableError, match="não respondeu"):
        asyncio.run(scenario())
    assert len(calls) == 1


def test_tts_body_reads_the_headlines_with_an_emphatic_style() -> None:
    turns = [
        Turn(speaker="Bia", text="Juros sobem de novo.", headline=True),
        Turn(speaker="Léo", text="Bom dia! Hoje é sexta-feira."),
    ]

    body = build_tts_body("gemini-3.8-flash-lite-tts", turns, HOSTS)

    content = body["input"][0]["content"]
    styles = [part["annotations"][0]["style"] for part in content]
    assert styles == [HEADLINE_TTS_STYLE, TTS_STYLE]


def test_rate_limit_without_a_suggested_delay_waits_half_a_minute(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    waits: list[float] = []
    calls: list[int] = []

    async def record(seconds: float) -> None:
        waits.append(seconds)

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        if len(calls) == 1:
            return httpx.Response(429, json={"error": {"message": "Rate limited"}})
        return httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": '{"ok": true}'}]}}]},
        )

    async def scenario() -> Any:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            data, _ = await GeminiClient(client, "key").generate_json(
                "gemini-3.8-flash", "system", "user", "selection"
            )
            return data

    monkeypatch.setattr(asyncio, "sleep", record)

    assert asyncio.run(scenario()) == {"ok": True}
    assert waits == [RATE_LIMIT_WAIT_SECONDS]

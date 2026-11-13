import asyncio
import base64
import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from pytest_django import Settings

from news_podcast.api.core.config import HOSTS
from news_podcast.api.core.retries import (
    MAX_ATTEMPTS,
    RATE_LIMIT_WAIT_SECONDS,
    backoff_seconds,
)
from news_podcast.api.core.schemas import Host, Turn, Usage
from news_podcast.api.core.voice.base import (
    VoiceError,
    VoiceQuotaExhaustedError,
    VoiceUnavailableError,
)
from news_podcast.api.core.voice.gemini import (
    GeminiVoice,
    build_tts_body,
    extract_audio_wav,
    pcm_to_wav,
    wav_duration,
)

MODEL = "gemini-3.8-flash-lite-tts"
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


@pytest.fixture(autouse=True)
def gemini_key(settings: Settings) -> None:
    settings.GEMINI_API_KEY = "test-key"


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


def synthesize_with(
    handler: Callable[[httpx.Request], httpx.Response], model: str = MODEL
) -> tuple[bytes, Usage]:
    async def scenario() -> tuple[bytes, Usage]:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await GeminiVoice(model, client).synthesize(
                [Turn(speaker="Bia", text="Oi")],
                HOSTS,
                style=STYLE,
                headline_style=HEADLINE_STYLE,
                step="voice",
            )

    return asyncio.run(scenario())


def record_waits(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    waits: list[float] = []

    async def record(seconds: float) -> None:
        waits.append(seconds)

    monkeypatch.setattr(asyncio, "sleep", record)
    return waits


def test_tts_body_uses_one_annotated_part_per_turn() -> None:
    turns = [Turn(speaker="Bia", text="Oi"), Turn(speaker="Léo", text="Olá")]

    body = build_tts_body("gemini-3.8-flash-tts", turns, HOSTS, STYLE, HEADLINE_STYLE)

    content = body["input"][0]["content"]
    assert [part["annotations"][0]["speaker"] for part in content] == ["Bia", "Leo"]
    assert body["generation_config"]["speech_config"]["speakers"] == [
        {"speaker": "Bia", "voice": "Kore"},
        {"speaker": "Leo", "voice": "Charon"},
    ]


def test_each_host_speaks_with_its_voice_for_google_genai() -> None:
    hosts = (
        Host(
            name="Ana",
            speaker_id="Ana",
            voices={"openai": "alloy", "google_genai": "Puck"},
        ),
        Host(name="Rui", speaker_id="Rui", voices={"google_genai": "Fenrir"}),
    )

    body = build_tts_body(
        MODEL, [Turn(speaker="Ana", text="Oi")], hosts, STYLE, HEADLINE_STYLE
    )

    assert body["generation_config"]["speech_config"]["speakers"] == [
        {"speaker": "Ana", "voice": "Puck"},
        {"speaker": "Rui", "voice": "Fenrir"},
    ]


def test_tts_body_reads_the_headlines_with_an_emphatic_style() -> None:
    turns = [
        Turn(speaker="Bia", text="Juros sobem de novo.", headline=True),
        Turn(speaker="Léo", text="Bom dia! Hoje é sexta-feira."),
    ]

    body = build_tts_body(MODEL, turns, HOSTS, STYLE, HEADLINE_STYLE)

    content = body["input"][0]["content"]
    styles = [part["annotations"][0]["style"] for part in content]
    assert styles == [HEADLINE_STYLE, STYLE]


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


@pytest.mark.parametrize("saved", [f"google_genai:{MODEL}", MODEL])
def test_the_request_names_the_model_without_its_provider(saved: str) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=AUDIO_ANSWER)

    audio, usage = synthesize_with(handler, saved)

    (request,) = requests
    assert request.url.path.endswith("/interactions")
    assert json.loads(request.content)["model"] == MODEL
    assert request.headers["x-goog-api-key"] == "test-key"
    assert wav_duration(audio) == pytest.approx(1.0)
    assert usage.step == "voice"
    assert usage.model == saved


def test_the_voice_needs_the_gemini_key(settings: Settings) -> None:
    settings.GEMINI_API_KEY = None

    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no request without the key")

    with pytest.raises(VoiceError, match="GEMINI_API_KEY"):
        synthesize_with(handler)


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

    audio, _ = synthesize_with(handler)

    assert wav_duration(audio) == pytest.approx(1.0)
    assert len(calls) == 2
    assert waits == [1.0]


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

    audio, _ = synthesize_with(handler)

    assert wav_duration(audio) == pytest.approx(1.0)
    assert waits == [RATE_LIMIT_WAIT_SECONDS]


def test_daily_quota_stops_without_retrying() -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        payload = json.loads(request.content)
        assert payload["response_format"] == {"type": "audio"}
        return httpx.Response(429, json=quota_error("RequestsPerDay-FreeTier"))

    with pytest.raises(VoiceQuotaExhaustedError) as caught:
        synthesize_with(handler)

    assert not isinstance(caught.value, VoiceUnavailableError)
    assert len(calls) == 1


def test_the_voice_gives_up_after_a_few_overloaded_attempts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record_waits(monkeypatch)
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(503, json={"error": {"message": "high demand"}})

    with pytest.raises(VoiceUnavailableError, match="503"):
        synthesize_with(handler)
    assert len(calls) == MAX_ATTEMPTS


def test_the_voice_gives_up_after_a_few_connection_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    waits = record_waits(monkeypatch)
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        raise httpx.ConnectError("connection refused", request=request)

    with pytest.raises(VoiceUnavailableError, match="Falha de conexão"):
        synthesize_with(handler)
    assert len(calls) == MAX_ATTEMPTS
    assert waits == [backoff_seconds(1), backoff_seconds(2)]


def test_the_voice_does_not_insist_after_a_timeout() -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        raise httpx.ReadTimeout("timed out", request=request)

    with pytest.raises(VoiceUnavailableError, match="não respondeu"):
        synthesize_with(handler)
    assert len(calls) == 1


def test_a_refused_request_fails_at_once() -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(400, json={"error": {"message": "bad voice"}})

    with pytest.raises(VoiceError, match="400") as caught:
        synthesize_with(handler)

    assert type(caught.value) is VoiceError
    assert len(calls) == 1


def test_an_answer_without_audio_fails_at_once() -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(200, json={"steps": []})

    with pytest.raises(VoiceError, match="não devolveu áudio") as caught:
        synthesize_with(handler)

    assert type(caught.value) is VoiceError
    assert len(calls) == 1

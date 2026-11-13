import asyncio
import base64
import io
import json
import logging
import re
import time
import wave
from collections.abc import Sequence
from typing import Any

import httpx

from news_podcast.api.core.config import AUDIO_TOKENS_PER_SECOND
from news_podcast.api.core.schemas import Host, Turn, Usage

logger = logging.getLogger(__name__)

API_ROOT = "https://generativelanguage.googleapis.com/v1beta"
MAX_ATTEMPTS = 3
MAX_RETRY_DELAY_SECONDS = 90.0
RATE_LIMIT_WAIT_SECONDS = 30.0
TEXT_TIMEOUT_SECONDS = 180.0
TTS_TIMEOUT_SECONDS = 180.0
MAX_OUTPUT_TOKENS = 32768
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})
PCM_SAMPLE_RATE = 24000
PCM_SAMPLE_WIDTH = 2
CHARS_PER_TOKEN = 4
SECONDS_PATTERN = re.compile(r"([\d.]+)s")
RATE_PATTERN = re.compile(r"rate=(\d+)")
INPUT_TOKEN_KEYS = (
    "total_input_tokens",
    "input_tokens",
    "promptTokenCount",
    "prompt_token_count",
)


class GeminiError(Exception):
    pass


class GeminiUnavailableError(GeminiError):
    pass


class GeminiQuotaExhaustedError(GeminiUnavailableError):
    pass


class GeminiClient:
    def __init__(self, http_client: httpx.AsyncClient, api_key: str) -> None:
        self.http_client = http_client
        self.api_key = api_key

    async def generate_json(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        step: str,
        thinking_level: str | None = None,
        *,
        schema: dict[str, Any],
    ) -> tuple[dict[str, Any], Usage]:
        """Returns the raw answer and its usage. Gemini can only write JSON that
        follows `schema`, a JSON Schema. The caller reads the JSON with answer_json()
        after counting the usage, because a broken answer is billed too."""
        generation_config: dict[str, Any] = {
            "responseMimeType": "application/json",
            "responseJsonSchema": schema,
            "maxOutputTokens": MAX_OUTPUT_TOKENS,
        }
        if thinking_level:
            generation_config["thinkingConfig"] = {"thinkingLevel": thinking_level}

        body = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": generation_config,
        }
        data = await self._post(
            f"{API_ROOT}/models/{model}:generateContent",
            body,
            TEXT_TIMEOUT_SECONDS,
            f"{model} ({step})",
        )
        return data, text_usage(data, step, model)

    async def synthesize_dialogue(
        self,
        model: str,
        turns: list[Turn],
        hosts: Sequence[Host],
        step: str,
        *,
        style: str,
        headline_style: str,
    ) -> tuple[bytes, Usage]:
        data = await self._post(
            f"{API_ROOT}/interactions",
            build_tts_body(model, turns, hosts, style, headline_style),
            TTS_TIMEOUT_SECONDS,
            f"{model} ({step})",
        )
        audio = extract_audio_wav(data)
        return audio, tts_usage(data, step, model, wav_duration(audio), turns)

    async def _post(
        self, url: str, body: dict[str, Any], timeout: float, label: str
    ) -> dict[str, Any]:
        for attempt in range(1, MAX_ATTEMPTS + 1):
            logger.info(
                f"Gemini {label}: waiting for a response "
                f"(attempt {attempt} of {MAX_ATTEMPTS}, up to {timeout:.0f}s)"
            )
            started = time.monotonic()
            response = await self._send(url, body, timeout, label, attempt)
            if response is None:
                continue
            if response.status_code == 200:
                elapsed = time.monotonic() - started
                logger.info(f"Gemini {label}: answered in {elapsed:.0f}s")
                return json_object(response)

            error = json_object(response)
            message = error_message(response.status_code, error)
            if response.status_code == 429 and is_daily_quota(error):
                raise GeminiQuotaExhaustedError(message)
            if response.status_code not in RETRYABLE_STATUS:
                raise GeminiError(message)
            if attempt == MAX_ATTEMPTS:
                raise GeminiUnavailableError(message)

            delay = wait_seconds(response.status_code, error, attempt)
            logger.warning(f"Gemini {label}: {message}; retrying in {delay:.0f}s")
            await asyncio.sleep(delay)

        raise GeminiUnavailableError(
            "O Gemini não respondeu depois de várias tentativas"
        )

    async def _send(
        self, url: str, body: dict[str, Any], timeout: float, label: str, attempt: int
    ) -> httpx.Response | None:
        try:
            return await self.http_client.post(
                url,
                json=body,
                headers={"x-goog-api-key": self.api_key},
                timeout=timeout,
            )
        except httpx.TimeoutException as error:
            raise GeminiUnavailableError(
                f"O Gemini não respondeu em {timeout:.0f}s"
            ) from error
        except httpx.TransportError as error:
            reason = f"{type(error).__name__} {error}".strip()
            if attempt == MAX_ATTEMPTS:
                raise GeminiUnavailableError(
                    f"Falha de conexão com o Gemini: {reason}"
                ) from error
            logger.warning(f"Gemini {label}: {reason}, retrying")
            await asyncio.sleep(backoff_seconds(attempt))
            return None


def backoff_seconds(attempt: int) -> float:
    return float(min(5 * 2 ** (attempt - 1), MAX_RETRY_DELAY_SECONDS))


def wait_seconds(status: int, error: dict[str, Any], attempt: int) -> float:
    suggested = retry_delay(error)
    if suggested is not None:
        return suggested
    if status == 429:
        return RATE_LIMIT_WAIT_SECONDS * attempt
    return backoff_seconds(attempt)


def json_object(response: httpx.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError:
        return {}
    return payload if isinstance(payload, dict) else {}


def error_details(error: dict[str, Any]) -> list[dict[str, Any]]:
    details = (error.get("error") or {}).get("details") or []
    return [detail for detail in details if isinstance(detail, dict)]


def is_daily_quota(error: dict[str, Any]) -> bool:
    for detail in error_details(error):
        for violation in detail.get("violations") or []:
            quota_id = str(violation.get("quotaId", ""))
            metric = str(violation.get("quotaMetric", ""))
            if "PerDay" in quota_id or "per_day" in metric:
                return True
    return False


def retry_delay(error: dict[str, Any]) -> float | None:
    for detail in error_details(error):
        match = SECONDS_PATTERN.fullmatch(str(detail.get("retryDelay", "")))
        if match:
            return min(float(match.group(1)) + 1, MAX_RETRY_DELAY_SECONDS)
    return None


def error_message(status: int, error: dict[str, Any]) -> str:
    message = str((error.get("error") or {}).get("message", ""))[:300]
    return f"Gemini respondeu {status}: {message}".strip()


def answer_json(data: dict[str, Any]) -> Any:
    return parse_json_text(extract_text(data))


def extract_text(data: dict[str, Any]) -> str:
    candidates = data.get("candidates") or []
    if not candidates:
        reason = (data.get("promptFeedback") or {}).get("blockReason", "sem resposta")
        raise GeminiError(f"O Gemini não gerou texto ({reason})")

    candidate = candidates[0]
    parts = (candidate.get("content") or {}).get("parts") or []
    text = "".join(
        str(part.get("text", "")) for part in parts if not part.get("thought")
    )
    finish_reason = candidate.get("finishReason", "")

    if finish_reason not in ("STOP", ""):
        logger.warning(f"Gemini stopped before the end of its answer: {finish_reason}")
    if not text.strip():
        raise GeminiError(f"O Gemini devolveu um texto vazio ({finish_reason})")
    return text


def parse_json_text(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        around = text[max(error.pos - 150, 0) : error.pos + 150]
        logger.warning(
            f"Gemini's JSON breaks at character {error.pos} of {len(text)} "
            f"({error.msg}): {around!r}"
        )
        raise GeminiError("O Gemini devolveu um JSON inválido") from error


def text_usage(data: dict[str, Any], step: str, model: str) -> Usage:
    metadata = data.get("usageMetadata") or {}
    output_tokens = int(metadata.get("candidatesTokenCount", 0)) + int(
        metadata.get("thoughtsTokenCount", 0)
    )
    return Usage(
        step=step,
        model=model,
        input_tokens=int(metadata.get("promptTokenCount", 0)),
        output_tokens=output_tokens,
    )


def build_tts_body(
    model: str,
    turns: list[Turn],
    hosts: Sequence[Host],
    style: str,
    headline_style: str,
) -> dict[str, Any]:
    speaker_ids = {host.name: host.speaker_id for host in hosts}
    content = [
        {
            "type": "text",
            "text": turn.text,
            "annotations": [
                {
                    "type": "speech_metadata",
                    "speaker": speaker_ids.get(turn.speaker, hosts[0].speaker_id),
                    "style": headline_style if turn.headline else style,
                }
            ],
        }
        for turn in turns
    ]
    speakers = [
        {"speaker": host.speaker_id, "voice": host.gemini_voice} for host in hosts
    ]
    return {
        "model": model,
        "input": [{"type": "user_input", "content": content}],
        "response_format": {"type": "audio"},
        "generation_config": {"speech_config": {"speakers": speakers}},
    }


def extract_audio_wav(data: dict[str, Any]) -> bytes:
    clips = [decode_clip(encoded, mime) for encoded, mime in find_audio_payloads(data)]
    if not clips:
        raise GeminiError("O Gemini não devolveu áudio")
    if len(clips) == 1:
        return clips[0]

    logger.warning(f"Gemini returned {len(clips)} audio clips, joining them")
    return pcm_to_wav(b"".join(wav_frames(clip) for clip in clips))


def find_audio_payloads(data: dict[str, Any]) -> list[tuple[str, str]]:
    payloads: list[tuple[str, str]] = []
    for step in data.get("steps") or []:
        if step.get("type") != "model_output":
            continue
        for content in step.get("content") or []:
            if content.get("type") == "audio" and content.get("data"):
                payloads.append(
                    (str(content["data"]), str(content.get("mime_type", "")))
                )
    if payloads:
        return payloads

    output_audio = data.get("output_audio") or {}
    if output_audio.get("data"):
        return [(str(output_audio["data"]), str(output_audio.get("mime_type", "")))]
    return []


def decode_clip(encoded: str, mime_type: str) -> bytes:
    raw = base64.b64decode(encoded)
    if raw[:4] == b"RIFF":
        return raw
    match = RATE_PATTERN.search(mime_type)
    return pcm_to_wav(raw, int(match.group(1)) if match else PCM_SAMPLE_RATE)


def pcm_to_wav(pcm: bytes, sample_rate: int = PCM_SAMPLE_RATE) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(PCM_SAMPLE_WIDTH)
        writer.setframerate(sample_rate)
        writer.writeframes(pcm)
    return buffer.getvalue()


def wav_frames(wav_bytes: bytes) -> bytes:
    with wave.open(io.BytesIO(wav_bytes), "rb") as reader:
        return reader.readframes(reader.getnframes())


def wav_duration(wav_bytes: bytes) -> float:
    with wave.open(io.BytesIO(wav_bytes), "rb") as reader:
        audio_bytes = len(reader.readframes(reader.getnframes()))
        bytes_per_second = (
            reader.getframerate() * reader.getnchannels() * reader.getsampwidth()
        )
    return audio_bytes / bytes_per_second


def tts_usage(
    data: dict[str, Any], step: str, model: str, seconds: float, turns: list[Turn]
) -> Usage:
    usage = data.get("usage") or {}
    reported_input = next(
        (
            int(usage[key])
            for key in INPUT_TOKEN_KEYS
            if isinstance(usage.get(key), int)
        ),
        0,
    )
    estimated_input = sum(len(turn.text) for turn in turns) // CHARS_PER_TOKEN
    return Usage(
        step=step,
        model=model,
        input_tokens=reported_input or estimated_input,
        output_tokens=round(seconds * AUDIO_TOKENS_PER_SECOND),
    )

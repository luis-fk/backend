from collections.abc import Callable

import httpx

from news_podcast.api.core.llm import split_model
from news_podcast.api.core.voice.base import VoiceError, VoiceProvider
from news_podcast.api.core.voice.gemini import GeminiVoice

# Each voice implementation, by LangChain's provider name. voice_provider builds from
# it and the admin checks the voice model against it, so a new provider is one entry
# here, plus each host's voice in HOSTS.
VOICE_PROVIDERS: dict[str, Callable[[str, httpx.AsyncClient], VoiceProvider]] = {
    "google_genai": GeminiVoice,
}


def voice_model_error(name: str) -> str | None:
    provider, model = split_model(name)
    if provider in VOICE_PROVIDERS and model.split() == [model]:
        return None
    return (
        f"Write provider:model with a voice provider ({', '.join(VOICE_PROVIDERS)}), "
        "such as google_genai:gemini-3.8-flash-lite-tts; a bare gemini-* name means "
        "google_genai."
    )


def voice_provider(model: str, http_client: httpx.AsyncClient) -> VoiceProvider:
    """The voice of the model's provider. The step that speaks builds it, so a bad
    name or a missing key fails that step, with its notice and history row."""
    if voice_model_error(model):
        examples = " ou ".join(f"{provider}:modelo" for provider in VOICE_PROVIDERS)
        raise VoiceError(f"{model} não é um modelo de voz conhecido; use {examples}")
    provider, _ = split_model(model)
    return VOICE_PROVIDERS[provider](model, http_client)

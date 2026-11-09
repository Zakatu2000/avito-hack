"""DeepSeek provider skeleton (task A0; real implementation in task A4).

Will use the OpenAI-compatible HTTP API with:
- base_url / model / key from environment only (see ai/.env.example);
- response_format={"type": "json_object"} and the word "json" in the prompt;
- finish_reason == "stop" required; empty content retried at most once
  within the overall timeout; 429/5xx/timeout -> provider_unavailable.

The httpx.AsyncClient is injected (one pool per process, created in the
FastAPI lifespan) - providers never build their own clients per call.
"""

import httpx

from providers.base import (
    LLMRequest,
    LLMResponse,
    ProviderConfigError,
    ProviderUnavailableError,
)
from settings import Settings


class DeepSeekProvider:
    def __init__(self, settings: Settings, http_client: httpx.AsyncClient) -> None:
        if settings.ai_mode == "live" and settings.deepseek_api_key is None:
            # Defensive: Settings validation normally makes this unreachable.
            raise ProviderConfigError(
                "AI_MODE=live requires DEEPSEEK_API_KEY (see ai/.env.example)"
            )
        self._settings = settings
        self._http = http_client

    async def complete(self, request: LLMRequest) -> LLMResponse:
        raise ProviderUnavailableError(
            "DeepSeekProvider.complete is implemented in task A4; "
            "use AI_MODE=demo for a reproducible offline run"
        )

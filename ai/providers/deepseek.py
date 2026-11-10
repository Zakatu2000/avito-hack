"""DeepSeek provider skeleton (real implementation in task A4).

Will use the OpenAI-compatible HTTP API with:
- base_url / model / key from environment only (see ai/.env.example);
- response_format={"type": "json_object"}, the word "json" and a JSON example
  in the prompt; model name comes only from DEEPSEEK_MODEL;
- finish_reason == "stop" required; empty content retried at most once
  within the overall timeout; 429/5xx/timeout -> provider_unavailable.

Synchronous httpx.Client is injected by the factory (one per process);
providers never build per-call clients. The client's timeout must stay below
the AgentRunner budget (server default: 10 s).
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
    def __init__(
        self, settings: Settings, http_client: httpx.Client | None = None
    ) -> None:
        if settings.ai_mode == "live" and settings.deepseek_api_key is None:
            # Defensive: Settings validation normally makes this unreachable.
            raise ProviderConfigError(
                "AI_MODE=live requires DEEPSEEK_API_KEY (see ai/.env.example)"
            )
        self._settings = settings
        self._http = http_client

    def complete(self, request: LLMRequest) -> LLMResponse:
        raise ProviderUnavailableError(
            "DeepSeekProvider.complete is implemented in task A4; "
            "run without BUDDY_AGENT_FACTORY for the deterministic demo mode"
        )

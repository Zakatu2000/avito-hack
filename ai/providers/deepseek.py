"""OpenAI-compatible chat-completions provider (task A4).

Confirmed against https://api-docs.deepseek.com (guides/json_mode,
api/create-chat-completion):
- response_format={"type": "json_object"}; the prompt must contain the word
  "json" and a JSON example (both are added here, not by callers);
- if the output is not recognized as JSON, the API replaces it with spaces
  (U+0020): content may be blank even with finish_reason="stop" -> retry once,
  then fail as provider_unavailable;
- finish_reason is passed through; the caller (policy, A3) accepts only
  "stop" and falls back deterministically otherwise;
- model name comes ONLY from settings (env) - never hard-coded.

The LLM returns a closed-set interpretation intent plus the formulated text
(LLMOutputSchema); the policy derives the decision from facts.

Failure policy: timeout / transport / HTTP error -> ProviderUnavailableError
immediately (the server turns it into 503 `unavailable`, S12); blank content
-> exactly one retry within the same call, then ProviderUnavailableError.
The httpx.Client is process-wide (injected by agent.factory). The API key is
read from the environment via Settings and is never logged.
"""

import httpx

from context.models import AiMode
from providers.base import (
    LLMRequest,
    LLMResponse,
    ProviderConfigError,
    ProviderUnavailableError,
)
from settings import Settings

_JSON_EXAMPLE = (
    '{"intent": "<blocker_access|ask_next_step|ask_request_status|ask_mentor'
    '|off_topic|unclear>", "text": "..."}'
)


class DeepSeekProvider:
    def __init__(
        self, settings: Settings, http_client: httpx.Client | None = None
    ) -> None:
        if settings.ai_mode == "live" and settings.deepseek_api_key is None:
            # Defensive: Settings validation normally makes this unreachable.
            raise ProviderConfigError(
                "AI_MODE=live requires AI_API_KEY (see ai/.env.example)"
            )
        self._settings = settings
        self._http = http_client or httpx.Client(
            timeout=settings.deepseek_timeout_seconds
        )

    def complete(self, request: LLMRequest) -> LLMResponse:
        settings = self._settings
        if not (
            settings.deepseek_base_url
            and settings.deepseek_model
            and settings.deepseek_api_key
        ):
            raise ProviderConfigError(
                "Incomplete provider config: AI_BASE_URL / AI_MODEL / "
                "AI_API_KEY are required (see ai/.env.example)"
            )

        url = settings.deepseek_base_url.rstrip("/") + "/chat/completions"
        headers = {
            "Authorization": "Bearer " + settings.deepseek_api_key.get_secret_value()
        }
        user_prompt = (
            f"Факты (json): {request.facts}\n\n"
            f"Вопрос стажёра: {request.user_message}\n\n"
            f"Ответь одним json-объектом по образцу: {_JSON_EXAMPLE}"
        )
        payload = {
            "model": settings.deepseek_model,
            "messages": [
                {"role": "system", "content": request.system_policy},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "max_tokens": request.max_output_tokens,
            "stream": False,
        }
        timeout = min(request.timeout_seconds, settings.deepseek_timeout_seconds)

        for _attempt in (1, 2):  # the second attempt exists only for blank content
            response = self._post(url, headers, payload, timeout)
            content, finish_reason = self._extract(response)
            if content and content.strip():
                return LLMResponse(
                    content=content, finish_reason=finish_reason, ai_mode=AiMode.LIVE
                )
        raise ProviderUnavailableError(
            "DeepSeek returned blank content twice (json mode space replacement)"
        )

    def _post(
        self, url: str, headers: dict, payload: dict, timeout: float
    ) -> httpx.Response:
        try:
            response = self._http.post(url, headers=headers, json=payload, timeout=timeout)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ProviderUnavailableError(
                f"deepseek http {exc.response.status_code}"
            ) from exc
        except httpx.HTTPError as exc:  # timeouts, DNS, connection errors
            raise ProviderUnavailableError(
                f"deepseek transport: {type(exc).__name__}"
            ) from exc
        return response

    @staticmethod
    def _extract(response: httpx.Response) -> tuple[str | None, str]:
        try:
            data = response.json()
            first = data["choices"][0]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ProviderUnavailableError("deepseek malformed response body") from exc
        message = first.get("message") or {}
        return message.get("content"), str(first.get("finish_reason") or "")

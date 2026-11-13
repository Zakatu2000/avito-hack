"""DeepSeek provider over mocked HTTP (httpx.MockTransport; no real calls).

Behavior confirmed against api-docs.deepseek.com (json mode guide):
blank/space-only content is retried exactly once, then provider_unavailable.
"""

import json

import httpx
import pytest
from pydantic import SecretStr

from context.models import AiMode
from providers.base import (
    LLMRequest,
    ProviderConfigError,
    ProviderUnavailableError,
)
from providers.deepseek import DeepSeekProvider
from settings import Settings


def make_settings() -> Settings:
    return Settings(
        _env_file=None,
        ai_mode="live",
        deepseek_base_url="https://example.invalid",
        deepseek_model="test-model",
        deepseek_api_key=SecretStr("test-key"),
    )


def make_request() -> LLMRequest:
    return LLMRequest(system_policy="policy", facts="{}", user_message="вопрос")


def make_provider(handler) -> tuple[DeepSeekProvider, list[httpx.Request]]:
    calls: list[httpx.Request] = []

    def handler_spy(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return handler(request)

    client = httpx.Client(transport=httpx.MockTransport(handler_spy))
    return DeepSeekProvider(make_settings(), client), calls


def completion(content: str | None, finish_reason: str = "stop") -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "choices": [
                {"message": {"content": content}, "finish_reason": finish_reason}
            ]
        },
    )


def test_success_sends_contract_shaped_request() -> None:
    provider, calls = make_provider(
        lambda _request: completion('{"intent": "unclear", "text": "ок"}')
    )

    response = provider.complete(make_request())

    assert response.ai_mode is AiMode.LIVE
    assert response.finish_reason == "stop"
    assert json.loads(response.content) == {"intent": "unclear", "text": "ок"}
    (request,) = calls
    assert request.url.path == "/chat/completions"
    assert request.headers["Authorization"] == "Bearer test-key"
    body = json.loads(request.content)
    assert body["model"] == "test-model"
    assert body["response_format"] == {"type": "json_object"}
    assert body["stream"] is False
    # json-mode prompt requirements: the word "json" and a JSON example.
    assert '"intent"' in body["messages"][1]["content"]


def test_custom_json_example_overrides_the_default() -> None:
    # The onboarding buddy chat uses a different closed intent set; the
    # response-format example must come from the request, not be hard-coded.
    provider, calls = make_provider(
        lambda _request: completion('{"intent": "next_step", "text": "ок"}')
    )
    request = LLMRequest(
        system_policy="policy",
        facts="{}",
        user_message="вопрос",
        json_example='{"intent": "<next_step|progress>", "text": "..."}',
    )
    provider.complete(request)
    body = json.loads(calls[0].content)
    prompt = body["messages"][1]["content"]
    assert "<next_step|progress>" in prompt
    assert "blocker_access" not in prompt


def test_blank_content_is_retried_once_then_succeeds() -> None:
    answers = iter(
        [completion("   "), completion('{"intent": "unclear", "text": "ок"}')]
    )
    provider, calls = make_provider(lambda _request: next(answers))
    response = provider.complete(make_request())
    assert json.loads(response.content)["intent"] == "unclear"
    assert len(calls) == 2


def test_blank_content_twice_is_provider_unavailable() -> None:
    provider, calls = make_provider(lambda _request: completion("  "))
    with pytest.raises(ProviderUnavailableError) as exc_info:
        provider.complete(make_request())
    assert exc_info.value.error_code == "provider_unavailable"
    assert len(calls) == 2  # exactly one retry, no more


@pytest.mark.parametrize("status", [429, 500, 503])
def test_http_errors_fail_fast_without_retry(status: int) -> None:
    provider, calls = make_provider(lambda _request: httpx.Response(status))
    with pytest.raises(ProviderUnavailableError, match=str(status)):
        provider.complete(make_request())
    assert len(calls) == 1


def test_timeout_is_provider_unavailable() -> None:
    def raise_timeout(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow")

    provider, calls = make_provider(raise_timeout)
    with pytest.raises(ProviderUnavailableError, match="transport"):
        provider.complete(make_request())
    assert len(calls) == 1


def test_malformed_body_is_provider_unavailable() -> None:
    provider, _calls = make_provider(
        lambda _request: httpx.Response(200, content=b"not json")
    )
    with pytest.raises(ProviderUnavailableError, match="malformed"):
        provider.complete(make_request())


def test_missing_choices_is_provider_unavailable() -> None:
    provider, _calls = make_provider(lambda _request: httpx.Response(200, json={}))
    with pytest.raises(ProviderUnavailableError, match="malformed"):
        provider.complete(make_request())


def test_incomplete_config_is_typed_error() -> None:
    settings = Settings(_env_file=None, ai_mode="demo")  # no deepseek_* values
    provider = DeepSeekProvider(settings)
    with pytest.raises(ProviderConfigError) as exc_info:
        provider.complete(make_request())
    assert exc_info.value.error_code == "provider_config_error"


def test_default_client_is_created_once_per_provider() -> None:
    provider = DeepSeekProvider(make_settings())
    assert isinstance(provider._http, httpx.Client)
    provider._http.close()


def test_live_mode_without_key_is_rejected_at_init() -> None:
    # Defensive branch: a Settings object flipped to live after construction.
    settings = Settings(_env_file=None, ai_mode="demo")
    settings.ai_mode = "live"
    with pytest.raises(ProviderConfigError) as exc_info:
        DeepSeekProvider(settings, httpx.Client())
    assert exc_info.value.error_code == "provider_config_error"

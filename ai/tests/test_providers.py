"""Provider contract: every implementation passes the SAME checks (plan A4).

The real provider is exercised through httpx.MockTransport - no real calls,
no key. A minimal in-process stub stands in for any other implementation.
"""

import json

import httpx
import pytest
from pydantic import SecretStr

from context.models import AiMode, LLMOutputSchema
from providers.base import LLMProvider, LLMRequest, LLMResponse
from providers.deepseek import DeepSeekProvider
from settings import Settings


def make_request() -> LLMRequest:
    return LLMRequest(
        system_policy="policy",
        facts='{"task": "demo"}',
        user_message="вопрос",
    )


class StubIntentProvider:
    """Smallest possible implementation of the provider port."""

    def complete(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(
            content=json.dumps(
                {"intent": "unclear", "text": "уточните, что не получается"},
                ensure_ascii=False,
            ),
            finish_reason="stop",
            ai_mode=AiMode.LIVE,
        )


def stub_provider() -> LLMProvider:
    return StubIntentProvider()


def live_provider() -> LLMProvider:
    settings = Settings(
        _env_file=None,
        ai_mode="live",
        deepseek_base_url="https://example.invalid",
        deepseek_model="test-model",
        deepseek_api_key=SecretStr("test-key"),
    )

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": '{"intent": "unclear", "text": "ок"}'
                        },
                        "finish_reason": "stop",
                    }
                ]
            },
        )

    return DeepSeekProvider(settings, httpx.Client(transport=httpx.MockTransport(handler)))


@pytest.mark.parametrize(
    ("factory", "expected_mode"),
    [(stub_provider, AiMode.LIVE), (live_provider, AiMode.LIVE)],
)
def test_providers_share_one_contract(factory, expected_mode: AiMode) -> None:
    response = factory().complete(make_request())
    assert isinstance(response, LLMResponse)
    assert response.ai_mode is expected_mode
    assert response.finish_reason == "stop"
    # Content always parses into the LLM output schema (validated again by policy).
    LLMOutputSchema.model_validate_json(response.content)


def test_stub_provider_is_deterministic_and_keyless() -> None:
    provider = StubIntentProvider()
    assert provider.complete(make_request()) == provider.complete(make_request())


def test_evals_package_is_importable() -> None:
    import evals  # noqa: F401

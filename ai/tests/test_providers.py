"""Provider contract: Demo and DeepSeek pass the SAME checks (plan A4).

DeepSeek is exercised through httpx.MockTransport - no real calls, no key.
"""

import json

import httpx
import pytest
from pydantic import SecretStr

from context.models import AiMode, LLMOutputSchema
from providers.base import LLMProvider, LLMRequest, LLMResponse
from providers.demo import DemoProvider
from providers.deepseek import DeepSeekProvider
from settings import Settings


def make_request() -> LLMRequest:
    return LLMRequest(
        system_policy="policy",
        facts='{"task": "demo"}',
        user_message="вопрос",
    )


def demo_provider() -> LLMProvider:
    return DemoProvider()


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
                        "message": {"content": '{"kind": "answer", "text": "ок"}'},
                        "finish_reason": "stop",
                    }
                ]
            },
        )

    return DeepSeekProvider(settings, httpx.Client(transport=httpx.MockTransport(handler)))


@pytest.mark.parametrize(
    ("factory", "expected_mode"),
    [(demo_provider, AiMode.DEMO), (live_provider, AiMode.LIVE)],
)
def test_providers_share_one_contract(factory, expected_mode: AiMode) -> None:
    response = factory().complete(make_request())
    assert isinstance(response, LLMResponse)
    assert response.ai_mode is expected_mode
    assert response.finish_reason == "stop"
    # Content always parses into the LLM output schema (validated again in A3).
    LLMOutputSchema.model_validate_json(response.content)


def test_demo_provider_is_deterministic_and_keyless() -> None:
    provider = DemoProvider()
    assert provider.complete(make_request()) == provider.complete(make_request())


def test_evals_package_is_importable() -> None:
    import evals  # noqa: F401

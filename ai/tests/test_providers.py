"""Provider skeletons: demo is deterministic and keyless; DeepSeek is typed."""

import json

import httpx
import pytest

from context.models import AiMode
from providers.base import (
    LLMRequest,
    ProviderConfigError,
    ProviderUnavailableError,
)
from providers.demo import DemoProvider
from providers.deepseek import DeepSeekProvider
from settings import Settings


def make_request() -> LLMRequest:
    return LLMRequest(
        system_policy="policy",
        facts='{"task": "demo"}',
        user_message="вопрос",
    )


def test_demo_provider_is_deterministic_and_keyless() -> None:
    provider = DemoProvider()
    first = provider.complete(make_request())
    second = provider.complete(make_request())
    assert first == second
    assert first.ai_mode is AiMode.DEMO
    assert first.finish_reason == "stop"
    payload = json.loads(first.content)
    assert set(payload) == {"kind", "text"}


def test_deepseek_complete_is_a_typed_skeleton_error() -> None:
    settings = Settings(_env_file=None, ai_mode="demo")
    provider = DeepSeekProvider(settings)
    with pytest.raises(ProviderUnavailableError) as exc_info:
        provider.complete(make_request())
    assert exc_info.value.error_code == "provider_unavailable"


def test_deepseek_rejects_live_mode_without_key() -> None:
    # Defensive branch: a Settings object flipped to live after construction.
    settings = Settings(_env_file=None, ai_mode="demo")
    settings.ai_mode = "live"
    with pytest.raises(ProviderConfigError) as exc_info:
        DeepSeekProvider(settings, httpx.Client())
    assert exc_info.value.error_code == "provider_config_error"


def test_evals_package_is_importable() -> None:
    import evals  # noqa: F401

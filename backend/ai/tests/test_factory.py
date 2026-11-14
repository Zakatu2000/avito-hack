"""Agent factory (BUDDY_AGENT_FACTORY integration point)."""

import pytest
from pydantic import SecretStr, ValidationError

from agent.factory import create_agent, create_provider
from agent.policy import BuddyAgent
from providers.deepseek import DeepSeekProvider
from settings import Settings


def test_factory_defaults_to_demo_without_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AI_MODE", raising=False)
    monkeypatch.delenv("AI_PROVIDER", raising=False)
    # _env_file=None: the developer's local ai/.env (pinned by settings.py)
    # must not leak into tests.
    agent = create_agent(Settings(_env_file=None))
    assert isinstance(agent, BuddyAgent)
    assert agent._provider is None


def test_factory_live_requires_full_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_MODE", "live")
    for name in (
        "AI_BASE_URL",
        "AI_MODEL",
        "AI_API_KEY",
        "DEEPSEEK_BASE_URL",
        "DEEPSEEK_MODEL",
        "DEEPSEEK_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(ValidationError):
        create_agent(Settings(_env_file=None))


def test_factory_live_builds_deepseek_backed_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AI_MODE", "live")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://example.invalid")
    monkeypatch.setenv("DEEPSEEK_MODEL", "model-name")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    agent = create_agent(Settings(_env_file=None))
    assert isinstance(agent, BuddyAgent)
    assert agent._provider is not None


def test_create_provider_is_none_in_demo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AI_MODE", raising=False)
    monkeypatch.delenv("AI_PROVIDER", raising=False)
    assert create_provider(Settings(_env_file=None)) is None


def test_create_provider_live_requires_full_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AI_MODE", "live")
    for name in (
        "AI_BASE_URL",
        "AI_MODEL",
        "AI_API_KEY",
        "DEEPSEEK_BASE_URL",
        "DEEPSEEK_MODEL",
        "DEEPSEEK_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(ValidationError):
        create_provider(Settings(_env_file=None))


def test_create_provider_live_builds_deepseek_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AI_MODE", "live")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://example.invalid")
    monkeypatch.setenv("DEEPSEEK_MODEL", "model-name")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    provider = create_provider(Settings(_env_file=None))
    assert isinstance(provider, DeepSeekProvider)
    provider._http.close()

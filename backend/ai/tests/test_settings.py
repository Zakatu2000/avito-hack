"""Settings: demo is the default; live without full config fails loudly.

Env naming: AI_* names are primary, DEEPSEEK_* names remain working aliases.
"""

import pytest
from pydantic import SecretStr, ValidationError

from settings import Settings


def test_default_mode_is_demo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AI_MODE", raising=False)
    monkeypatch.delenv("AI_PROVIDER", raising=False)
    settings = Settings(_env_file=None)
    assert settings.ai_mode == "demo"
    assert settings.ai_provider == "openai_compatible"


def test_live_mode_requires_full_config() -> None:
    with pytest.raises(ValidationError, match="AI_API_KEY"):
        Settings(_env_file=None, ai_mode="live")
    with pytest.raises(ValidationError, match="AI_MODEL"):
        Settings(
            _env_file=None,
            ai_mode="live",
            deepseek_api_key=SecretStr("k"),
            deepseek_base_url="https://example.invalid",
        )


def test_live_mode_with_full_config() -> None:
    settings = Settings(
        _env_file=None,
        ai_mode="live",
        deepseek_api_key=SecretStr("k"),
        deepseek_base_url="https://example.invalid",
        deepseek_model="model-name",
    )
    assert settings.ai_mode == "live"
    assert settings.deepseek_timeout_seconds == 8.0
    # Neutral accessors for the OpenAI-compatible provider config.
    assert settings.provider_base_url == "https://example.invalid"
    assert settings.provider_model == "model-name"
    assert settings.provider_api_key == SecretStr("k")
    assert settings.provider_timeout_seconds == 8.0


def test_env_ai_names_are_primary(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "AI_BASE_URL", "AI_MODEL", "AI_API_KEY", "AI_TIMEOUT_SECONDS",
        "DEEPSEEK_BASE_URL", "DEEPSEEK_MODEL", "DEEPSEEK_API_KEY",
        "DEEPSEEK_TIMEOUT_SECONDS",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("AI_BASE_URL", "https://one.example")
    monkeypatch.setenv("AI_MODEL", "m1")
    monkeypatch.setenv("AI_API_KEY", "k1")
    monkeypatch.setenv("AI_TIMEOUT_SECONDS", "5")
    settings = Settings(_env_file=None)
    assert settings.deepseek_base_url == "https://one.example"
    assert settings.deepseek_model == "m1"
    assert settings.deepseek_api_key == SecretStr("k1")
    assert settings.deepseek_timeout_seconds == 5.0


def test_env_deepseek_aliases_still_work(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "AI_BASE_URL", "AI_MODEL", "AI_API_KEY", "AI_TIMEOUT_SECONDS",
        "DEEPSEEK_BASE_URL", "DEEPSEEK_MODEL", "DEEPSEEK_API_KEY",
        "DEEPSEEK_TIMEOUT_SECONDS",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://two.example")
    monkeypatch.setenv("DEEPSEEK_MODEL", "m2")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "k2")
    monkeypatch.setenv("DEEPSEEK_TIMEOUT_SECONDS", "6")
    settings = Settings(_env_file=None)
    assert settings.deepseek_base_url == "https://two.example"
    assert settings.deepseek_model == "m2"
    assert settings.deepseek_api_key == SecretStr("k2")
    assert settings.deepseek_timeout_seconds == 6.0

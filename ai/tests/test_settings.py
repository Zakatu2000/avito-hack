"""Settings: demo is the default; live without full config fails loudly."""

import pytest
from pydantic import SecretStr, ValidationError

from settings import Settings


def test_default_mode_is_demo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AI_MODE", raising=False)
    monkeypatch.delenv("AI_PROVIDER", raising=False)
    settings = Settings(_env_file=None)
    assert settings.ai_mode == "demo"
    assert settings.ai_provider == "deepseek"


def test_live_mode_requires_full_config() -> None:
    with pytest.raises(ValidationError, match="DEEPSEEK_API_KEY"):
        Settings(_env_file=None, ai_mode="live")
    with pytest.raises(ValidationError, match="DEEPSEEK_MODEL"):
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
    assert settings.deepseek_timeout_seconds == 15.0

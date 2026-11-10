"""Runtime configuration of the AI service (task A0).

Values come from environment variables / ai/.env only. No secrets or exact
endpoints are hard-coded in source; see ai/.env.example for the template.

Provider naming: the live provider is ANY OpenAI-compatible chat-completions
endpoint. Primary env names are AI_BASE_URL / AI_MODEL / AI_API_KEY /
AI_TIMEOUT_SECONDS; the DEEPSEEK_* names remain supported as aliases (the
first name found in the environment wins, AI_* checked first).

Invariant (plan.md A4): AI_MODE=live without a complete provider config is a
startup error - the service must NOT silently masquerade as demo.
"""

from typing import Literal

from pydantic import AliasChoices, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    ai_provider: Literal["openai_compatible", "deepseek", "demo"] = "openai_compatible"
    ai_mode: Literal["demo", "live"] = "demo"

    deepseek_base_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("ai_base_url", "deepseek_base_url"),
    )
    deepseek_model: str | None = Field(
        default=None,
        validation_alias=AliasChoices("ai_model", "deepseek_model"),
    )
    deepseek_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("ai_api_key", "deepseek_api_key"),
    )
    deepseek_timeout_seconds: float = Field(
        default=8.0,
        validation_alias=AliasChoices("ai_timeout_seconds", "deepseek_timeout_seconds"),
    )

    @property
    def provider_base_url(self) -> str | None:
        return self.deepseek_base_url

    @property
    def provider_model(self) -> str | None:
        return self.deepseek_model

    @property
    def provider_api_key(self) -> SecretStr | None:
        return self.deepseek_api_key

    @property
    def provider_timeout_seconds(self) -> float:
        return self.deepseek_timeout_seconds

    @model_validator(mode="after")
    def _live_mode_requires_full_config(self) -> "Settings":
        if self.ai_mode == "live":
            missing = [
                name
                for name, value in (
                    ("AI_BASE_URL", self.deepseek_base_url),
                    ("AI_MODEL", self.deepseek_model),
                    ("AI_API_KEY", self.deepseek_api_key),
                )
                if not value
            ]
            if missing:
                raise ValueError(
                    "AI_MODE=live requires "
                    + ", ".join(missing)
                    + " (DEEPSEEK_* aliases are accepted); set them or switch "
                    "to AI_MODE=demo"
                )
        return self

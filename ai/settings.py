"""Runtime configuration of the AI service (task A0).

Values come from environment variables / ai/.env only. No secrets or exact
endpoints are hard-coded in source; see ai/.env.example for the template.

Invariant (plan.md A4): AI_MODE=live without a complete DeepSeek config is a
startup error - the service must NOT silently masquerade as demo.
"""

from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ai_provider: Literal["deepseek", "demo"] = "deepseek"
    ai_mode: Literal["demo", "live"] = "demo"

    deepseek_base_url: str | None = None
    deepseek_model: str | None = None
    deepseek_api_key: SecretStr | None = None
    deepseek_timeout_seconds: float = 8.0

    @model_validator(mode="after")
    def _live_mode_requires_full_config(self) -> "Settings":
        if self.ai_mode == "live":
            missing = [
                name
                for name, value in (
                    ("DEEPSEEK_BASE_URL", self.deepseek_base_url),
                    ("DEEPSEEK_MODEL", self.deepseek_model),
                    ("DEEPSEEK_API_KEY", self.deepseek_api_key),
                )
                if not value
            ]
            if missing:
                raise ValueError(
                    "AI_MODE=live requires "
                    + ", ".join(missing)
                    + "; set them or switch to AI_MODE=demo"
                )
        return self

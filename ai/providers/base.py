"""Provider interface and typed errors (task A0 skeleton; behavior in A4).

DemoProvider and DeepSeekProvider must pass the SAME contract tests, so the
demo mode stays a faithful rehearsal of the live path.
"""

from typing import Protocol

from context.models import AiMode, ContractModel


class LLMRequest(ContractModel):
    """Everything a provider may see.

    `facts` is a pre-filtered serialization of trusted facts: no secrets, no
    internal roles, no unfiltered instruction texts (filtering is task A2).
    """

    system_policy: str
    facts: str
    user_message: str
    max_output_tokens: int = 800
    timeout_seconds: float = 15.0


class LLMResponse(ContractModel):
    content: str  # raw JSON string; parsed and validated by the caller (A3)
    finish_reason: str  # caller must require "stop" (A4)
    ai_mode: AiMode


class LLMProvider(Protocol):
    async def complete(self, request: LLMRequest) -> LLMResponse:
        """Single completion call. Retries/timeouts are the impl's concern."""
        ...


class ProviderError(RuntimeError):
    """Base typed provider error; error_code is part of AgentResult."""

    def __init__(self, message: str, *, error_code: str) -> None:
        super().__init__(message)
        self.error_code = error_code


class ProviderConfigError(ProviderError):
    def __init__(self, message: str) -> None:
        super().__init__(message, error_code="provider_config_error")


class ProviderUnavailableError(ProviderError):
    def __init__(self, message: str) -> None:
        super().__init__(message, error_code="provider_unavailable")

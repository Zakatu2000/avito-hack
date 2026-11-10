"""Provider interface and typed errors (task A4; skeleton aligned in A0.1).

Synchronous: the agent runs inside the server's AgentRunner thread pool
(contracts/agent.md, server/dialog.py). Providers never create per-call
clients - a process-wide httpx.Client is injected by the factory (A4).

Every provider implementation must pass the SAME contract tests, so live
behaviour stays a faithful rehearsal of the demo path.
"""

from typing import Protocol

from context.models import AiMode, ContractModel


class LLMRequest(ContractModel):
    """Everything a provider may see.

    `facts` is a pre-filtered serialization of trusted facts: no secrets, no
    internal roles, no unfiltered instruction texts (filtering is task A2/A3).
    """

    system_policy: str
    facts: str
    user_message: str
    max_output_tokens: int = 800
    timeout_seconds: float = 8.0


class LLMResponse(ContractModel):
    content: str  # raw JSON string; parsed and validated by the caller (A3)
    finish_reason: str  # caller must require "stop" (A4)
    ai_mode: AiMode


class LLMProvider(Protocol):
    def complete(self, request: LLMRequest) -> LLMResponse:
        """Single completion call. Retries/timeouts are the impl's concern."""
        ...


class ProviderError(RuntimeError):
    """Base typed provider error; error_code is part of the surfaced state."""

    def __init__(self, message: str, *, error_code: str) -> None:
        super().__init__(message)
        self.error_code = error_code


class ProviderConfigError(ProviderError):
    def __init__(self, message: str) -> None:
        super().__init__(message, error_code="provider_config_error")


class ProviderUnavailableError(ProviderError):
    def __init__(self, message: str) -> None:
        super().__init__(message, error_code="provider_unavailable")

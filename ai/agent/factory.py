"""Agent factory - the integration point for the server (task B4).

Wire in the server environment:

    BUDDY_AGENT_FACTORY=agent.factory:create_agent

Server rule (server/app.py): a configured factory means mode "live" and the
server rejects decisions whose aiMode differs. Therefore set
BUDDY_AGENT_FACTORY only together with AI_MODE=live (+AI_* provider config).
Demo mode is simply the absence of the factory (server-side DemoAgent).

Requires `pip install -e ai` (or PYTHONPATH=ai) so `agent.factory` imports.
"""

import httpx

from agent.policy import BuddyAgent
from context.models import AiMode
from providers.deepseek import DeepSeekProvider
from settings import Settings


def create_provider(settings: Settings | None = None) -> DeepSeekProvider | None:
    """Live LLM provider for server call sites outside AgentRunner.

    The onboarding buddy chat (/api/buddy/chat) uses the provider directly for
    text formulation inside the server's deterministic routing. Returns None in
    demo mode; live without full AI_* config raises via Settings validation.
    """
    settings = settings or Settings()
    if settings.ai_mode != "live":
        return None
    # One client per call site; timeout stays below the caller's budget.
    client = httpx.Client(timeout=settings.deepseek_timeout_seconds)
    return DeepSeekProvider(settings, client)


def create_agent(settings: Settings | None = None) -> BuddyAgent:
    # The server import-string contract calls this with no arguments; tests
    # inject Settings(_env_file=None) to stay independent of a local ai/.env.
    settings = settings or Settings()
    provider = create_provider(settings)
    if provider is not None:
        return BuddyAgent(AiMode.LIVE, provider)
    return BuddyAgent(AiMode.DEMO)

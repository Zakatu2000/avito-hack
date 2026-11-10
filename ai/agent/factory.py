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


def create_agent(settings: Settings | None = None) -> BuddyAgent:
    # The server import-string contract calls this with no arguments; tests
    # inject Settings(_env_file=None) to stay independent of a local ai/.env.
    settings = settings or Settings()
    if settings.ai_mode == "live":
        # One process-wide client; timeout stays below the AgentRunner budget.
        client = httpx.Client(timeout=settings.deepseek_timeout_seconds)
        return BuddyAgent(AiMode.LIVE, DeepSeekProvider(settings, client))
    return BuddyAgent(AiMode.DEMO)

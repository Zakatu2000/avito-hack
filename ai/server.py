"""OPTIONAL FastAPI adapter of the AI service (standalone runs / debugging).

Primary integration is IN-PROCESS: the Flask server loads the agent via the
BUDDY_AGENT_FACTORY import string and calls Agent.respond inside AgentRunner
(contracts/agent.md). This HTTP adapter mirrors the same contract for local
development and does not add a parallel one:

- GET  /health               - liveness only; reveals NO configuration;
- POST /internal/ai/respond  - body {text, workspace} (openapi.yaml Workspace),
                               returns the raw AgentDecision dict.

The service is internal: it never sees browser cookies, never connects to
PostgreSQL and never mutates requests/rights (the server owns all writes).
The sync agent runs in the threadpool so the event loop is never blocked.

Run from this directory:
    uvicorn server:app --reload --port 8100
"""

from typing import Any

from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool

from agent.policy import BuddyAgent
from context.models import AgentRespondRequest, AiMode, ContractModel
from context.tools import WorkspaceTools
from settings import Settings

SERVICE_VERSION = "0.1.0"


class HealthResponse(ContractModel):
    """Liveness payload. Deliberately carries no config/mode information."""

    status: str = "ok"


def create_app(settings: Settings | None = None, agent: Any = None) -> FastAPI:
    settings = settings or Settings()
    agent = agent if agent is not None else BuddyAgent(AiMode(settings.ai_mode))

    app = FastAPI(
        title="ai-buddy-ai",
        version=SERVICE_VERSION,
        # Internal service behind the backend: no public docs/schema endpoints.
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.settings = settings
    app.state.agent = agent

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse()

    @app.post("/internal/ai/respond")
    async def respond(body: AgentRespondRequest) -> dict[str, Any]:
        tools = WorkspaceTools(body.workspace)
        return await run_in_threadpool(agent.respond, body.text, tools)

    return app


app = create_app()

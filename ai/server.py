"""FastAPI adapter of the AI service (task A0).

Endpoints:
- GET  /health               - liveness only; reveals NO configuration;
- POST /internal/ai/respond  - typed Agent.respond port (stub until task A3).

The service is internal: it is called by the backend server with a trusted
AgentContext. It never sees browser cookies, never connects to PostgreSQL
and never mutates requests/rights (the server owns all writes).

Run from this directory:
    uvicorn server:app --reload --port 8100
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from context.models import (
    ActionType,
    AgentRespondRequest,
    AgentResult,
    ContractModel,
    SourceType,
)
from settings import Settings

SERVICE_VERSION = "0.0.0"


class HealthResponse(ContractModel):
    """Liveness payload. Deliberately carries no config/mode information."""

    status: str = "ok"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # One HTTP pool per process, shared by providers (see A4).
        async with httpx.AsyncClient() as client:
            app.state.http_client = client
            yield

    app = FastAPI(
        title="ai-buddy-ai",
        version=SERVICE_VERSION,
        # Internal service behind the backend: no public docs/schema endpoints.
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.settings = settings

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse()

    @app.post(
        "/internal/ai/respond",
        response_model=AgentResult,
        response_model_by_alias=True,
    )
    async def respond(body: AgentRespondRequest) -> AgentResult:
        # A0: no orchestration yet (task A3). Return an explicit typed stub
        # with an error code - never a fake successful answer.
        return AgentResult(
            text=(
                "AI-оркестрация пока не реализована (этап A3). "
                "Это типизированный ответ-заглушка этапа A0."
            ),
            source=SourceType.NONE,
            next_step=None,
            action_type=ActionType.NONE,
            request_status=body.context.request.request_status,
            effective_access=body.context.access.effective_access,
            ai_mode=settings.ai_mode,
            error_code="agent_not_implemented",
        )

    return app


app = create_app()

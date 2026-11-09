"""Shared fixtures for the AI zone tests.

The payload fixtures double as the LOCAL TYPED FIXTURE for the provisional
contract (contracts/ is owned by team task B1 and does not exist yet).
"""

import pytest
from fastapi.testclient import TestClient

from server import create_app
from settings import Settings


@pytest.fixture()
def demo_settings() -> Settings:
    # Explicit and deterministic: never depends on the developer's env.
    return Settings(_env_file=None, ai_provider="demo", ai_mode="demo")


@pytest.fixture()
def client(demo_settings: Settings) -> TestClient:
    app = create_app(demo_settings)
    with TestClient(app) as test_client:  # runs lifespan (pool create/close)
        yield test_client


@pytest.fixture()
def base_context_payload() -> dict:
    """Intern with an assigned task, allowed instruction, NO effective right."""
    return {
        "sessionId": "sess-0001",
        "assignmentId": "assign-0001",
        "correlationId": "corr-0001",
        "task": {
            "state": "known",
            "taskId": "task-0001",
            "title": "Первый PR (учебная задача)",
            "resourceId": "repo-learning-101",
        },
        "instruction": {
            "state": "known",
            "resourceId": "repo-learning-101",
            "fragment": "Учебный фрагмент инструкции (синтетические данные).",
            "sourceRef": "docs/sdd/sources.md#provisional",
        },
        "access": {
            "state": "known",
            "resourceId": "repo-learning-101",
            "effectiveAccess": "none",
        },
        "request": {"state": "unknown"},
    }


@pytest.fixture()
def respond_payload(base_context_payload: dict) -> dict:
    return {
        "context": base_context_payload,
        "userMessage": "Не могу открыть учебный репозиторий. Что делать?",
    }

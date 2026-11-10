"""Shared fixtures for the AI zone tests.

The workspace fixture mirrors contracts/examples/initial.json (owner: Web 2).
The living binding to the authoritative files is test_contract_examples.py.
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
    with TestClient(app) as test_client:  # runs startup/shutdown
        yield test_client


@pytest.fixture()
def workspace_initial() -> dict:
    """Intern: task assigned, allowed instruction, NO effective right, no request."""
    return {
        "task": {
            "taskId": "task-01",
            "title": "Открыть README учебного репозитория",
            "resourceId": "repo-intro",
        },
        "source": {
            "sourceId": "demo-guide",
            "excerpt": "Учебная инструкция. Подтвердите заявку на доступ к назначенному репозиторию.",
        },
        "effectiveAccess": "missing",
        "request": None,
        "nextStep": "Спросите помощника о первом шаге",
    }


@pytest.fixture()
def respond_payload(workspace_initial: dict) -> dict:
    return {
        "text": "Не могу открыть учебный репозиторий. Что делать?",
        "workspace": workspace_initial,
    }

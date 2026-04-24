"""
Integration-test defaults: avoid requiring a live PostgreSQL for FastAPI lifespan startup.
"""

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from backend.app.core.database import get_db


async def _integration_refresh_stub(instance, attribute_names=None, with_for_update=None):
    """Simulate DB refresh so ORM instances satisfy response schemas without a real engine."""
    from datetime import datetime, timezone
    from uuid import uuid4

    from backend.app.models.analysis import Analysis
    from backend.app.models.project import Project, ProjectStatus
    from backend.app.models.user import User

    now = datetime.now(timezone.utc)

    if isinstance(instance, User):
        if getattr(instance, "id", None) is None:
            instance.id = uuid4()
        instance.is_active = True
        instance.is_verified = False
        if getattr(instance, "settings", None) is None:
            instance.settings = {}
        instance.created_at = now
        instance.updated_at = now
    elif isinstance(instance, Project):
        if getattr(instance, "id", None) is None:
            instance.id = uuid4()
        instance.created_at = now
        instance.updated_at = now
        if getattr(instance, "status", None) is None:
            instance.status = ProjectStatus.ACTIVE
        if getattr(instance, "collaborators", None) is None:
            instance.collaborators = []
        if getattr(instance, "project_metadata", None) is None:
            instance.project_metadata = {}
    elif isinstance(instance, Analysis):
        if getattr(instance, "id", None) is None:
            instance.id = uuid4()
        instance.created_at = now
        instance.updated_at = now
        if getattr(instance, "progress", None) is None:
            instance.progress = 0.0
        if getattr(instance, "total_steps", None) is None:
            instance.total_steps = 0


@pytest.fixture
def db_override(mock_db_session, test_client):
    """Inject ``mock_db_session`` via FastAPI dependency overrides (patching route modules does not work)."""
    from backend.app.main import app

    async def _override():
        yield mock_db_session

    app.dependency_overrides[get_db] = _override
    prev_refresh = mock_db_session.refresh
    mock_db_session.refresh = _integration_refresh_stub
    yield mock_db_session
    mock_db_session.refresh = prev_refresh
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def test_client(monkeypatch):
    """ASGI test client with database lifespan hooks no-op'd (CI/local without Postgres)."""
    # Patch names bound in ``main`` (``from database import init_db`` keeps the original
    # reference if only ``database.init_db`` is replaced).
    monkeypatch.setattr("backend.app.main.init_db", AsyncMock())
    monkeypatch.setattr("backend.app.main.close_db", AsyncMock())
    from backend.app.main import app

    with TestClient(app) as client:
        yield client

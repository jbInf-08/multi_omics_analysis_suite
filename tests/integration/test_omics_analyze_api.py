"""Integration tests for POST /api/v1/omics/modules/{module}/analyze."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from backend.app.core.security import TokenPayload, get_current_user
from backend.app.main import app


def _token_payload(sub: str) -> TokenPayload:
    now = datetime.now(timezone.utc)
    return TokenPayload(
        sub=sub,
        exp=now + timedelta(hours=1),
        iat=now,
        type="access",
    )


def _configure_execute_returns_project(session_mock, project):
    exec_result = MagicMock()
    exec_result.scalar_one_or_none = MagicMock(return_value=project)
    session_mock.execute = AsyncMock(return_value=exec_result)


@pytest.fixture
def mock_project_for_owner():
    project = MagicMock()
    project.owner_id = uuid4()
    project.id = uuid4()
    return project


@pytest.fixture
def auth_as_owner(mock_project_for_owner):
    async def _user():
        return _token_payload(str(mock_project_for_owner.owner_id))

    app.dependency_overrides[get_current_user] = _user
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def auth_as_intruder():
    async def _user():
        return _token_payload(str(uuid4()))

    app.dependency_overrides[get_current_user] = _user
    yield
    app.dependency_overrides.pop(get_current_user, None)


def test_omics_analyze_unknown_module(test_client, auth_headers, db_override):
    response = test_client.post(
        "/api/v1/omics/modules/no_such_module_xyz/analyze",
        headers=auth_headers,
        json={
            "project_id": str(uuid4()),
            "analysis_type": "clustering",
            "parameters": {},
            "dataset_ids": [],
        },
    )
    assert response.status_code == 404


def test_omics_analyze_invalid_analysis_type(
    test_client, auth_headers, db_override, mock_project_for_owner, auth_as_owner
):
    _configure_execute_returns_project(db_override, mock_project_for_owner)
    response = test_client.post(
        "/api/v1/omics/modules/single_cell/analyze",
        headers=auth_headers,
        json={
            "project_id": str(mock_project_for_owner.id),
            "analysis_type": "not_a_real_analysis_name",
            "parameters": {},
            "dataset_ids": [],
        },
    )
    assert response.status_code == 400


def test_omics_analyze_forbidden_wrong_owner(
    test_client, auth_headers, db_override, auth_as_intruder
):
    mock_project = MagicMock()
    mock_project.owner_id = uuid4()
    mock_project.id = uuid4()
    _configure_execute_returns_project(db_override, mock_project)
    response = test_client.post(
        "/api/v1/omics/modules/single_cell/analyze",
        headers=auth_headers,
        json={
            "project_id": str(mock_project.id),
            "analysis_type": "clustering",
            "parameters": {},
            "dataset_ids": [],
        },
    )
    assert response.status_code == 403


def test_omics_analyze_queues_task(
    test_client, auth_headers, db_override, mock_project_for_owner, auth_as_owner
):
    _configure_execute_returns_project(db_override, mock_project_for_owner)
    db_override.commit = AsyncMock()
    db_override.refresh = AsyncMock()

    fake_task = MagicMock()
    fake_task.id = "omics-test-task-id"

    with patch("backend.app.tasks.analysis_tasks.run_analysis") as mock_run:
        mock_run.apply_async = MagicMock(return_value=fake_task)
        response = test_client.post(
            "/api/v1/omics/modules/single_cell/analyze",
            headers=auth_headers,
            json={
                "project_id": str(mock_project_for_owner.id),
                "analysis_type": "clustering",
                "parameters": {"k": 10},
                "dataset_ids": [],
            },
        )

    assert response.status_code == 201
    body = response.json()
    assert body.get("celery_task_id") == "omics-test-task-id"
    assert body.get("status") == "queued"
    mock_run.apply_async.assert_called_once()

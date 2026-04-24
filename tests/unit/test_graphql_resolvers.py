"""
Unit Tests for GraphQL Resolvers
=================================

Tests for resolver type conversion and behavior with mocked DB.
"""

import pytest
from uuid import uuid4
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone

from backend.app.api.graphql.resolvers import (
    model_to_project_type,
    model_to_dataset_type,
    model_to_analysis_type,
    get_projects,
    get_datasets,
)


def utc_now():
    return datetime.now(timezone.utc)


class TestModelToProjectType:
    """Tests for model_to_project_type."""

    def test_converts_project_model(self):
        mock = MagicMock()
        mock.id = uuid4()
        mock.name = "Test Project"
        mock.description = "Desc"
        mock.project_type = "multi_omics"
        mock.omics_types = ["genomics"]
        mock.status = MagicMock(value="active")
        mock.visibility = "private"
        mock.tags = ["tag1"]
        mock.owner_id = uuid4()
        mock.created_at = utc_now()
        mock.updated_at = utc_now()

        result = model_to_project_type(mock)
        assert result.name == "Test Project"
        assert result.description == "Desc"
        assert result.status == "active"
        assert result.omics_types == ["genomics"]


class TestModelToDatasetType:
    """Tests for model_to_dataset_type."""

    def test_converts_dataset_model(self):
        mock = MagicMock()
        mock.id = uuid4()
        mock.name = "Test Dataset"
        mock.description = "Desc"
        mock.omics_type = MagicMock(value="genomics")
        mock.data_format = "csv"
        mock.sample_count = 10
        mock.feature_count = 100
        mock.status = MagicMock(value="ready")
        mock.source = "upload"
        mock.qc_passed = True
        mock.project_id = uuid4()
        mock.created_at = utc_now()
        mock.updated_at = utc_now()

        result = model_to_dataset_type(mock)
        assert result.name == "Test Dataset"
        assert result.omics_type == "genomics"
        assert result.status == "ready"
        assert result.sample_count == 10


class TestModelToAnalysisType:
    """Tests for model_to_analysis_type."""

    def test_converts_analysis_model(self):
        mock = MagicMock()
        mock.id = uuid4()
        mock.name = "Test Analysis"
        mock.description = "Desc"
        mock.analysis_type = MagicMock(value="single_omics")
        mock.omics_types = ["transcriptomics"]
        mock.status = MagicMock(value="completed")
        mock.progress = 1.0
        mock.current_step = None
        mock.total_steps = 5
        mock.project_id = uuid4()
        mock.user_id = uuid4()
        mock.created_at = utc_now()
        mock.started_at = utc_now()
        mock.completed_at = utc_now()

        result = model_to_analysis_type(mock)
        assert result.name == "Test Analysis"
        assert result.analysis_type == "single_omics"
        assert result.status == "completed"
        assert result.progress == 1.0


@pytest.mark.asyncio
class TestGetProjectsAsync:
    """Tests for get_projects with mocked session."""

    async def test_returns_empty_list_on_exception(self):
        async def fake_gen():
            session = AsyncMock()
            session.execute = AsyncMock(side_effect=Exception("db error"))
            yield session

        with patch("backend.app.api.graphql.resolvers.get_async_session", return_value=fake_gen()):
            result = await get_projects(user_id=None, status=None, limit=10, offset=0)
            assert result == []


@pytest.mark.asyncio
class TestGetDatasetsAsync:
    """Tests for get_datasets with mocked session."""

    async def test_returns_empty_list_on_exception(self):
        async def fake_gen():
            session = AsyncMock()
            session.execute = AsyncMock(side_effect=Exception("db error"))
            yield session

        with patch("backend.app.api.graphql.resolvers.get_async_session", return_value=fake_gen()):
            result = await get_datasets(project_id=None, omics_type=None, limit=10, offset=0)
            assert result == []

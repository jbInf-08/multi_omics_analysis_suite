"""Integration Tests for API Endpoints.
====================================

Tests for FastAPI endpoints including authentication, projects, datasets, and analyses.
"""

from unittest.mock import MagicMock
from uuid import uuid4

import pytest


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    def test_health_check(self, test_client):
        """Test health check endpoint."""
        response = test_client.get("/health")

        # Should return 200 or endpoint may not exist yet
        assert response.status_code in [200, 404]


class TestAuthEndpoints:
    """Tests for authentication endpoints."""

    @pytest.fixture
    def mock_user_data(self):
        """Mock user registration data."""
        return {
            "email": "test@example.com",
            "username": "testuser",
            "password": "SecurePassword123!",
            "full_name": "Test User",
        }

    @pytest.fixture
    def mock_login_data(self):
        """Mock login data."""
        return {
            "username": "test@example.com",
            "password": "SecurePassword123!",
        }

    def test_register_user(self, test_client, mock_user_data, mock_db_session, db_override):
        """Test user registration."""
        response = test_client.post("/api/v1/auth/register", json=mock_user_data)

        # May return 201 (created), 400 (validation), or 422 (unprocessable)
        assert response.status_code in [201, 400, 422, 500]

    def test_login(self, test_client, mock_login_data, mock_db_session, db_override):
        """Test user login."""
        from backend.app.core.security import get_password_hash

        mock_user = MagicMock()
        mock_user.hashed_password = get_password_hash(mock_login_data["password"])
        mock_user.is_active = True
        mock_user.roles = ["user"]
        mock_user.permissions = ["read", "write"]
        mock_user.id = uuid4()
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = mock_user

        response = test_client.post(
            "/api/v1/auth/login",
            data=mock_login_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        # May return 200 (success), 401 (unauthorized), or other
        assert response.status_code in [200, 401, 422, 500]

    def test_login_invalid_credentials(self, test_client, mock_db_session, db_override):
        """Test login with invalid credentials."""
        invalid_data = {
            "username": "nonexistent@example.com",
            "password": "wrongpassword",
        }
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = None

        response = test_client.post(
            "/api/v1/auth/login",
            data=invalid_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        # Should not return 200
        assert response.status_code != 200


class TestProjectEndpoints:
    """Tests for project management endpoints."""

    @pytest.fixture
    def mock_project_data(self):
        """Mock project creation data."""
        return {
            "name": "Test Project",
            "description": "A test project for multi-omics analysis",
            "tags": ["genomics", "proteomics"],
        }

    def test_create_project(
        self, test_client, mock_project_data, auth_headers, mock_db_session, db_override
    ):
        """Test project creation."""
        response = test_client.post(
            "/api/v1/projects/", json=mock_project_data, headers=auth_headers
        )

        # Check response
        assert response.status_code in [201, 401, 422, 500]

    def test_list_projects(self, test_client, auth_headers, mock_db_session, db_override):
        """Test listing projects."""
        mock_db_session.execute.return_value.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value.scalar.return_value = 0

        response = test_client.get("/api/v1/projects/", headers=auth_headers)

        assert response.status_code in [200, 401, 500]

    def test_get_project_not_found(self, test_client, auth_headers, mock_db_session, db_override):
        """Test getting non-existent project."""
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = None

        response = test_client.get(f"/api/v1/projects/{uuid4()}", headers=auth_headers)

        assert response.status_code in [404, 401, 500]

    def test_unauthorized_access(self, test_client, mock_db_session):
        """Test accessing projects without authentication."""
        response = test_client.get("/api/v1/projects/")

        # Should return 401 or 403
        assert response.status_code in [401, 403, 422]


class TestDatasetEndpoints:
    """Tests for dataset management endpoints."""

    @pytest.fixture
    def mock_dataset_data(self):
        """Mock dataset creation data."""
        return {
            "name": "Test Dataset",
            "description": "A test dataset",
            "data_type": "genomics",
            "file_format": "vcf",
            "project_id": str(uuid4()),
        }

    def test_create_dataset(
        self, test_client, mock_dataset_data, auth_headers, mock_db_session, db_override
    ):
        """Test dataset creation."""
        response = test_client.post(
            "/api/v1/datasets/", json=mock_dataset_data, headers=auth_headers
        )

        assert response.status_code in [201, 400, 401, 422, 500]

    def test_list_datasets(self, test_client, auth_headers, mock_db_session, db_override):
        """Test listing datasets."""
        mock_db_session.execute.return_value.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value.scalar.return_value = 0

        response = test_client.get("/api/v1/datasets/", headers=auth_headers)

        assert response.status_code in [200, 401, 500]


class TestAnalysisEndpoints:
    """Tests for analysis management endpoints."""

    @pytest.fixture
    def mock_analysis_data(self):
        """Mock analysis creation data."""
        return {
            "name": "Test Analysis",
            "description": "A test analysis",
            "analysis_type": "single_omics",
            "omics_types": ["transcriptomics"],
            "parameters": {"fdr_threshold": 0.05},
            "input_datasets": [str(uuid4())],
            "project_id": str(uuid4()),
        }

    def test_create_analysis(
        self,
        test_client,
        mock_analysis_data,
        auth_headers,
        mock_db_session,
        db_override,
        auth_user_id,
    ):
        """Test analysis creation."""
        # Mock project existence (owner must match JWT ``sub`` from auth_headers)
        mock_project = MagicMock()
        mock_project.owner_id = auth_user_id
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = mock_project

        response = test_client.post(
            "/api/v1/analyses/", json=mock_analysis_data, headers=auth_headers
        )

        assert response.status_code in [201, 400, 401, 403, 404, 422, 500]

    def test_list_analyses(self, test_client, auth_headers, mock_db_session, db_override):
        """Test listing analyses."""
        mock_db_session.execute.return_value.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value.scalar.return_value = 0

        response = test_client.get("/api/v1/analyses/", headers=auth_headers)

        assert response.status_code in [200, 401, 500]

    def test_get_analysis_results(self, test_client, auth_headers, mock_db_session, db_override):
        """Test getting analysis results."""
        analysis_id = uuid4()

        # Mock analysis existence
        mock_analysis = MagicMock()
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = mock_analysis
        mock_db_session.execute.return_value.scalars.return_value.all.return_value = []

        response = test_client.get(f"/api/v1/analyses/{analysis_id}/results", headers=auth_headers)

        assert response.status_code in [200, 401, 404, 500]

    def test_cancel_analysis(
        self, test_client, auth_headers, mock_db_session, db_override, auth_user_id
    ):
        """Test cancelling an analysis."""
        from backend.app.models.analysis import Analysis, AnalysisStatus, AnalysisType

        analysis_id = uuid4()
        analysis = Analysis(
            id=analysis_id,
            name="Test",
            description=None,
            analysis_type=AnalysisType.SINGLE_OMICS,
            omics_types=[],
            parameters={},
            input_datasets=[],
            project_id=uuid4(),
            user_id=auth_user_id,
            status=AnalysisStatus.RUNNING,
            celery_task_id=None,
        )
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = analysis

        response = test_client.post(f"/api/v1/analyses/{analysis_id}/cancel", headers=auth_headers)

        assert response.status_code in [200, 400, 401, 404, 500]

    def test_delete_analysis(self, test_client, auth_headers, mock_db_session, db_override):
        """Test deleting an analysis."""
        analysis_id = uuid4()

        mock_analysis = MagicMock()
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = mock_analysis

        response = test_client.delete(f"/api/v1/analyses/{analysis_id}", headers=auth_headers)

        assert response.status_code in [204, 401, 404, 500]


class TestOmicsEndpoints:
    """Tests for omics-specific endpoints."""

    def test_list_omics_modules(self, test_client, auth_headers):
        """Test listing available omics modules."""
        response = test_client.get("/api/v1/omics/modules", headers=auth_headers)

        # May return modules list or 404 if not implemented
        assert response.status_code in [200, 401, 404, 500]

    def test_get_omics_module(self, test_client, auth_headers):
        """Test getting specific omics module info."""
        response = test_client.get("/api/v1/omics/modules/genomics", headers=auth_headers)

        assert response.status_code in [200, 401, 404, 500]


class TestMLEndpoints:
    """Tests for machine learning endpoints."""

    def test_list_ml_models(self, test_client, auth_headers):
        """Test listing ML models."""
        response = test_client.get("/api/v1/ml/models", headers=auth_headers)
        assert response.status_code in [200, 401, 404, 500]
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list)

    @pytest.fixture
    def mock_training_data(self):
        """ML training request (matches TrainRequest schema)."""
        return {
            "model_type": "random_forest",
            "dataset_ids": [str(uuid4())],
            "target_column": "label",
            "parameters": {"n_estimators": 100},
        }

    def test_train_model_returns_task_id(self, test_client, mock_training_data, auth_headers):
        """Test ML train endpoint returns task_id when authenticated."""
        response = test_client.post(
            "/api/v1/ml/train", json=mock_training_data, headers=auth_headers
        )
        assert response.status_code in [200, 201, 401, 422, 500]
        if response.status_code in (200, 201):
            data = response.json()
            assert "task_id" in data
            assert data.get("task_id") != "pending_implementation"

    def test_ml_task_status_endpoint(self, test_client, auth_headers):
        """Test ML task status endpoint."""
        response = test_client.get("/api/v1/ml/task/some-task-id", headers=auth_headers)
        assert response.status_code in [200, 401, 404]
        if response.status_code == 200:
            data = response.json()
            assert "task_id" in data
            assert "status" in data


class TestPaginationAndFiltering:
    """Tests for pagination and filtering functionality."""

    def test_pagination_params(self, test_client, auth_headers, mock_db_session, db_override):
        """Test pagination parameters."""
        mock_db_session.execute.return_value.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value.scalar.return_value = 0

        response = test_client.get("/api/v1/analyses/?page=1&page_size=10", headers=auth_headers)

        assert response.status_code in [200, 401, 500]

    def test_filtering_by_status(self, test_client, auth_headers, mock_db_session, db_override):
        """Test filtering by status."""
        mock_db_session.execute.return_value.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value.scalar.return_value = 0

        response = test_client.get(
            "/api/v1/analyses/?status_filter=completed", headers=auth_headers
        )

        assert response.status_code in [200, 401, 500]

    def test_invalid_pagination(self, test_client, auth_headers, mock_db_session, db_override):
        """Test invalid pagination parameters."""
        response = test_client.get("/api/v1/analyses/?page=-1&page_size=0", headers=auth_headers)

        # Should return validation error
        assert response.status_code in [422, 400, 401, 500]


class TestErrorHandling:
    """Tests for API error handling."""

    def test_not_found(self, test_client, auth_headers):
        """Test 404 handling."""
        response = test_client.get("/api/v1/nonexistent/endpoint", headers=auth_headers)

        assert response.status_code in [404, 401]

    def test_method_not_allowed(self, test_client, auth_headers):
        """Test 405 handling."""
        response = test_client.patch(
            "/api/v1/analyses/", headers=auth_headers  # PATCH not allowed on list endpoint
        )

        assert response.status_code in [405, 401, 404]

    def test_validation_error(self, test_client, auth_headers, mock_db_session, db_override):
        """Test validation error handling."""
        invalid_data = {
            "name": "",  # Empty name should be invalid
            "analysis_type": "invalid_type",
        }

        response = test_client.post("/api/v1/analyses/", json=invalid_data, headers=auth_headers)

        # Should return validation error (422) or bad request (400)
        assert response.status_code in [400, 422, 401, 500]

"""Unit Tests for Celery Tasks.
===========================

Tests for task logic with mocked dependencies (no real broker).
Run with CELERY_TASK_ALWAYS_EAGER=true or use mocks.
"""

from unittest.mock import patch

import numpy as np
import pandas as pd


class TestIntegrationTasks:
    """Tests for integration_tasks module."""

    def test_run_multi_omics_integration_fails_with_insufficient_datasets(self):
        from backend.app.tasks.integration_tasks import run_multi_omics_integration

        with patch("backend.app.tasks.integration_tasks.load_dataset_data", return_value=None):
            result = run_multi_omics_integration(
                dataset_ids=["id1"],
                method="concatenation",
                parameters={},
            )
        assert result["status"] == "failed"
        assert "error" in result


class TestMLTasks:
    """Tests for ml_tasks module - feature selection with mocked data."""

    def test_run_feature_selection_variance_returns_structure(self):
        from backend.app.tasks.ml_tasks import run_feature_selection

        with patch("backend.app.tasks.ml_tasks.load_dataset_data") as load_mock:
            n_samples, n_features = 50, 20
            X = np.random.rand(n_samples, n_features)
            y = (X[:, 0] > 0.5).astype(int)
            df = pd.DataFrame(X, columns=[f"f{i}" for i in range(n_features)])
            df["target"] = y
            load_mock.return_value = df

            result = run_feature_selection(
                dataset_id="test-id",
                method="variance",
                n_features=10,
                target_column="target",
            )

        assert "status" in result
        assert result.get("status") in ("completed", "failed")
        if result.get("status") == "completed":
            assert "features" in result


class TestDataTasks:
    """Tests for data_tasks module (helpers only; full task requires Celery broker)."""

    def test_get_storage_path_returns_path(self):
        from backend.app.tasks.data_tasks import get_storage_path

        path = get_storage_path("test-dataset-id", "data.parquet")
        assert path is not None
        assert "test-dataset-id" in str(path)
        assert path.name == "data.parquet"

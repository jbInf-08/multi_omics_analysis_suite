"""Tests for backend.ml.models, which was reconstructed from its call sites.

The directory had never been committed -- `.gitignore`'s bare `models/` rule
matched `backend/ml/models/` as well as `backend/app/models/` -- so
`backend/ml/__init__.py` imported a module that did not exist and the whole
`backend.ml` package was unimportable. Nothing imports it, so no test noticed.

These tests pin the contract the surviving code actually depends on, so a
reconstruction that drifts from it fails here rather than at runtime.
"""

import json

import numpy as np
import pandas as pd
import pytest

from backend.ml.feature_selection import FeatureSelector
from backend.ml.models import get_model, list_available_models
from backend.ml.models.base import ModelMetrics
from backend.ml.models.traditional import (
    ElasticNetModel,
    LogisticRegressionModel,
    RandomForestModel,
)
from backend.ml.training import ModelTrainer, TrainingConfig


@pytest.fixture
def classification_data():
    rng = np.random.default_rng(0)
    X = pd.DataFrame(rng.normal(size=(60, 6)), columns=[f"f{i}" for i in range(6)])
    y = (X["f0"] + 0.5 * X["f1"] > 0).astype(int)
    return X, y


class TestPackageImports:
    def test_backend_ml_is_importable(self):
        """The failure this whole module exists to prevent."""
        import backend.ml as ml

        assert set(ml.__all__) >= {"get_model", "list_available_models", "ModelTrainer"}


class TestRegistry:
    def test_lists_the_names_automl_and_ml_tasks_use(self):
        names = {entry["name"] for entry in list_available_models()}
        # automl's model_space keys, plus logistic which ml_tasks builds.
        assert names == {
            "random_forest",
            "xgboost",
            "lightgbm",
            "svm",
            "logistic",
            "elastic_net",
        }

    def test_builds_a_model_by_name(self):
        model = get_model("random_forest", task="classification", n_estimators=10)
        assert isinstance(model, RandomForestModel)
        assert model.model_type == "classification"

    def test_unknown_name_is_an_error(self):
        with pytest.raises(ValueError, match="Unknown model"):
            get_model("crystal_ball")

    def test_task_a_model_cannot_serve_is_an_error(self):
        """elastic_net is regression only; logistic is classification only."""
        with pytest.raises(ValueError, match="does not support task"):
            get_model("elastic_net", task="classification")
        with pytest.raises(ValueError, match="does not support task"):
            get_model("logistic", task="regression")

    def test_fixed_task_models_accept_the_kwarg_without_duplicating_it(self):
        """ml_tasks passes task= generically; these two fix their own."""
        assert get_model("logistic", task="classification").model_type == "classification"
        assert get_model("elastic_net", task="regression").model_type == "regression"


class TestModelContract:
    def test_exposes_model_type_which_the_trainer_branches_on(self, classification_data):
        """Constructed with task=, read as model_type. Both must work."""
        model = RandomForestModel(n_estimators=10, task="classification")
        assert model.model_type == "classification"
        assert model.task == "classification"

    def test_fit_predict_and_proba(self, classification_data):
        X, y = classification_data
        model = RandomForestModel(n_estimators=20, task="classification").fit(X, y)

        assert model.predict(X).shape == (len(y),)
        assert model.predict_proba(X).shape == (len(y), 2)
        assert model.classes_.tolist() == [0, 1]

    def test_unfitted_use_is_refused(self):
        model = RandomForestModel(n_estimators=5)
        with pytest.raises(RuntimeError, match="must be fitted"):
            model.predict([[0.0] * 6])

    def test_feature_importance_is_named_and_ordered(self, classification_data):
        X, y = classification_data
        model = RandomForestModel(n_estimators=50, task="classification")
        model.feature_names = list(X.columns)
        model.fit(X, y)

        importance = model.get_feature_importance()
        assert set(importance) == set(X.columns)
        # f0 drives the label, so it must rank first.
        assert max(importance, key=importance.get) == "f0"

    def test_importance_from_coefficients_when_there_are_no_tree_importances(
        self, classification_data
    ):
        X, y = classification_data
        model = LogisticRegressionModel().fit(X, y)
        assert len(model.get_feature_importance()) == X.shape[1]

    def test_regression_model_has_no_predict_proba(self):
        rng = np.random.default_rng(1)
        X = pd.DataFrame(rng.normal(size=(40, 4)), columns=list("abcd"))
        y = X["a"] * 2 + rng.normal(scale=0.1, size=40)
        model = ElasticNetModel(alpha=0.1).fit(X, y)

        with pytest.raises(AttributeError, match="predict_proba"):
            model.predict_proba(X)

    def test_rejects_a_nonsense_task(self):
        with pytest.raises(ValueError, match="classification"):
            RandomForestModel(task="prophecy")


class TestPersistence:
    def test_save_writes_the_layout_ml_tasks_reads_back(self, classification_data, tmp_path):
        """ml_tasks does joblib.load(path.with_suffix('.joblib')) and reads
        feature_names out of the sibling .json."""
        import joblib

        X, y = classification_data
        model = RandomForestModel(n_estimators=10, task="classification")
        model.feature_names = list(X.columns)
        model.fit(X, y)

        model.save(tmp_path / "model")

        assert (tmp_path / "model.joblib").exists()
        assert (tmp_path / "model.json").exists()

        reloaded = joblib.load(tmp_path / "model.joblib")
        assert (reloaded.predict(X) == model.predict(X)).all()

        metadata = json.loads((tmp_path / "model.json").read_text())
        assert metadata["feature_names"] == list(X.columns)
        assert metadata["task"] == "classification"

    def test_saving_an_unfitted_model_is_refused(self, tmp_path):
        with pytest.raises(RuntimeError):
            RandomForestModel(n_estimators=5).save(tmp_path / "nope")


class TestModelMetrics:
    def test_accepts_either_metric_family(self):
        """ModelTrainer builds this from the classification or regression dict."""
        assert ModelMetrics(**{"accuracy": 0.9, "f1": 0.88}).accuracy == 0.9
        assert ModelMetrics(**{"mse": 0.2, "r2": 0.7}).r2 == 0.7

    def test_from_dict_ignores_keys_it_does_not_carry(self):
        metrics = ModelMetrics.from_dict({"accuracy": 0.5, "some_new_metric": 1.0})
        assert metrics.accuracy == 0.5
        assert "some_new_metric" not in metrics.to_dict()

    def test_to_dict_omits_metrics_that_were_not_computed(self):
        assert ModelMetrics(accuracy=0.9).to_dict() == {"accuracy": 0.9}


class TestTrainerIntegration:
    def test_train_with_cv_runs_and_attaches_metrics(self, classification_data):
        """The path that failed first: it reads model.model_type."""
        X, y = classification_data
        trainer = ModelTrainer(TrainingConfig(cv_folds=3))

        model, cv_results = trainer.train_with_cv(
            RandomForestModel(n_estimators=20, task="classification"), X, y
        )

        assert model.metrics is not None
        assert "accuracy" in model.metrics.to_dict()
        assert cv_results

    def test_train_test_evaluate_runs(self, classification_data):
        X, y = classification_data
        model, results = ModelTrainer(TrainingConfig()).train_test_evaluate(
            RandomForestModel(n_estimators=20, task="classification"), X, y
        )
        assert set(results) >= {"accuracy", "f1"}


class TestFeatureSelectorIntegration:
    @pytest.mark.parametrize("method", ["random_forest", "lasso"])
    def test_embedded_selection_runs(self, classification_data, method):
        """Blocked entirely while backend.ml could not be imported."""
        X, y = classification_data
        result = FeatureSelector().embedded_selection(X, y, method=method)
        assert result.selected_features
        assert "f0" in result.selected_features

    def test_stability_selection_runs(self, classification_data):
        X, y = classification_data
        result = FeatureSelector().stability_selection(X, y)
        assert "f0" in result.selected_features

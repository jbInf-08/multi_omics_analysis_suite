"""Base model interface for the ML engine.

Reconstructed from how the package is used, not recovered from an original:
`.gitignore`'s bare `models/` rule matched `backend/ml/models/` as well as
`backend/app/models/`, so this directory was never committed and is absent from
the remote. Everything here is pinned by an existing call site --
`backend/ml/training.py` constructs ModelMetrics from the metric dicts it
computes, and `backend/app/tasks/ml_tasks.py` calls fit/predict/predict_proba,
save and get_feature_importance. Reconcile against the originals if they exist.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


@dataclass
class ModelMetrics:
    """Evaluation metrics for a fitted model.

    Every field is optional because ModelTrainer builds this with
    ``ModelMetrics(**results)`` from either the classification or the regression
    metric dict, and from cross-validation aggregates that may include only a
    subset. Unknown keys are dropped by :meth:`from_dict` rather than raising,
    so a new metric appearing upstream does not break training.
    """

    # Classification
    accuracy: float | None = None
    precision: float | None = None
    recall: float | None = None
    f1: float | None = None
    auc_roc: float | None = None
    auc_pr: float | None = None
    # Regression
    mse: float | None = None
    rmse: float | None = None
    mae: float | None = None
    r2: float | None = None

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> ModelMetrics:
        """Build from a metric dict, ignoring keys this class does not carry."""
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in values.items() if k in known})

    def to_dict(self) -> dict[str, float]:
        """Only the metrics that were actually computed."""
        return {k: v for k, v in asdict(self).items() if v is not None}


class BaseModel(ABC):
    """Common surface for the models the tasks and trainer drive.

    Wraps an estimator rather than subclassing one: the call sites treat these
    as plain objects with fit/predict, and also hang ``feature_names`` and
    ``metrics`` on them, which scikit-learn estimators reject under their
    parameter validation.
    """

    def __init__(self, task: str = "classification", random_state: int = 42) -> None:
        if task not in ("classification", "regression"):
            raise ValueError(f"task must be 'classification' or 'regression', got {task!r}")
        # Constructed with `task=` (ml_tasks) but read as `model_type`
        # (training.py). Both names refer to the same value; model_type is the
        # stored one because that is what the trainer branches on.
        self.model_type = task
        self.random_state = random_state
        self.model: Any = None
        self.feature_names: list[str] | None = None
        self.metrics: ModelMetrics | None = None
        self.is_fitted = False

    @property
    def task(self) -> str:
        """Alias for :attr:`model_type`, the name the constructors use."""
        return self.model_type

    @property
    def name(self) -> str:
        return type(self).__name__

    @property
    def classes_(self) -> Any:
        """Delegate to the estimator; ml_tasks reads this after prediction."""
        self._require_fitted()
        return self.model.classes_

    @property
    def feature_importances_(self) -> Any:
        self._require_fitted()
        return self.model.feature_importances_

    @property
    def coef_(self) -> Any:
        self._require_fitted()
        return self.model.coef_

    @abstractmethod
    def _build(self) -> Any:
        """Return the underlying estimator for this task."""

    def fit(self, X, y) -> BaseModel:
        if self.model is None:
            self.model = self._build()
        if self.feature_names is None and isinstance(X, pd.DataFrame):
            self.feature_names = [str(c) for c in X.columns]
        self.model.fit(np.asarray(X), np.asarray(y))
        self.is_fitted = True
        return self

    def _require_fitted(self) -> None:
        if not self.is_fitted or self.model is None:
            raise RuntimeError(f"{self.name} must be fitted before use")

    def predict(self, X) -> np.ndarray:
        self._require_fitted()
        return self.model.predict(np.asarray(X))

    def predict_proba(self, X) -> np.ndarray:
        """Class probabilities.

        Raises for regression tasks and for estimators without the method,
        rather than inventing a value; ml_tasks guards this call with a task
        check already.
        """
        self._require_fitted()
        if not hasattr(self.model, "predict_proba"):
            raise AttributeError(f"{self.name} does not provide predict_proba")
        return self.model.predict_proba(np.asarray(X))

    def get_feature_importance(self) -> dict[str, float]:
        """Importance per feature, or an empty dict when the estimator has none.

        Callers treat a falsy result as "not available" rather than as zero
        importance, so an empty dict is the honest answer for models that expose
        neither feature_importances_ nor coef_.
        """
        if not self.is_fitted or self.model is None:
            return {}

        if hasattr(self.model, "feature_importances_"):
            values = np.asarray(self.model.feature_importances_, dtype=float)
        elif hasattr(self.model, "coef_"):
            coef = np.asarray(self.model.coef_, dtype=float)
            values = np.abs(coef).sum(axis=0) if coef.ndim > 1 else np.abs(coef)
        else:
            return {}

        names = self.feature_names or [f"feature_{i}" for i in range(len(values))]
        if len(names) != len(values):
            names = [f"feature_{i}" for i in range(len(values))]
        return {n: float(v) for n, v in zip(names, values, strict=False)}

    def save(self, path: str | Path) -> Path:
        """Persist to ``<path>.joblib`` with metadata at ``<path>.json``.

        The suffixes are dictated by ml_tasks, which loads the model with
        ``joblib.load(model_path.with_suffix(".joblib"))`` and reads
        ``feature_names`` back out of the sibling ``.json``.
        """
        import joblib

        self._require_fitted()
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        model_file = path.with_suffix(".joblib")
        joblib.dump(self, model_file)

        metadata = {
            "model": self.name,
            "task": self.model_type,
            "random_state": self.random_state,
            "feature_names": self.feature_names or [],
            "metrics": self.metrics.to_dict() if self.metrics else {},
        }
        with open(path.with_suffix(".json"), "w", encoding="utf-8") as handle:
            json.dump(metadata, handle, indent=2)

        return model_file

    @staticmethod
    def load(path: str | Path) -> BaseModel:
        import joblib

        return joblib.load(Path(path).with_suffix(".joblib"))

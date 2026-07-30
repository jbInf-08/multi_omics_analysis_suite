"""Traditional (non-deep) models.

Reconstructed from call sites -- see the note in base.py. The constructor
signatures here are fixed by backend/app/tasks/ml_tasks.py, which builds each of
these with a specific set of keyword arguments.

xgboost and lightgbm are imported lazily: they are heavy, and a deployment that
never selects them should not pay for the import or fail without them.
"""

from __future__ import annotations

from typing import Any

from backend.ml.models.base import BaseModel


class RandomForestModel(BaseModel):
    """Random forest classifier or regressor."""

    def __init__(
        self,
        n_estimators: int = 100,
        max_depth: int | None = None,
        task: str = "classification",
        random_state: int = 42,
        **kwargs: Any,
    ) -> None:
        super().__init__(task=task, random_state=random_state)
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.kwargs = kwargs

    def _build(self) -> Any:
        from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor

        cls = RandomForestClassifier if self.task == "classification" else RandomForestRegressor
        return cls(
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            random_state=self.random_state,
            n_jobs=-1,
            **self.kwargs,
        )


class XGBoostModel(BaseModel):
    """Gradient boosted trees via xgboost."""

    def __init__(
        self,
        n_estimators: int = 100,
        max_depth: int = 6,
        learning_rate: float = 0.1,
        task: str = "classification",
        random_state: int = 42,
        **kwargs: Any,
    ) -> None:
        super().__init__(task=task, random_state=random_state)
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.learning_rate = learning_rate
        self.kwargs = kwargs

    def _build(self) -> Any:
        from xgboost import XGBClassifier, XGBRegressor

        cls = XGBClassifier if self.task == "classification" else XGBRegressor
        return cls(
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            learning_rate=self.learning_rate,
            random_state=self.random_state,
            n_jobs=-1,
            **self.kwargs,
        )


class LightGBMModel(BaseModel):
    """Gradient boosted trees via lightgbm."""

    def __init__(
        self,
        n_estimators: int = 100,
        max_depth: int = -1,
        learning_rate: float = 0.1,
        task: str = "classification",
        random_state: int = 42,
        **kwargs: Any,
    ) -> None:
        super().__init__(task=task, random_state=random_state)
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.learning_rate = learning_rate
        self.kwargs = kwargs

    def _build(self) -> Any:
        from lightgbm import LGBMClassifier, LGBMRegressor

        cls = LGBMClassifier if self.task == "classification" else LGBMRegressor
        return cls(
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            learning_rate=self.learning_rate,
            random_state=self.random_state,
            n_jobs=-1,
            verbose=-1,
            **self.kwargs,
        )


class SVMModel(BaseModel):
    """Support vector classifier or regressor."""

    def __init__(
        self,
        C: float = 1.0,
        kernel: str = "rbf",
        task: str = "classification",
        random_state: int = 42,
        **kwargs: Any,
    ) -> None:
        super().__init__(task=task, random_state=random_state)
        self.C = C
        self.kernel = kernel
        self.kwargs = kwargs

    def _build(self) -> Any:
        from sklearn.svm import SVC, SVR

        if self.task == "classification":
            # probability=True so predict_proba is available; the tasks call it
            # whenever the task is classification.
            return SVC(
                C=self.C,
                kernel=self.kernel,
                probability=True,
                random_state=self.random_state,
                **self.kwargs,
            )
        return SVR(C=self.C, kernel=self.kernel, **self.kwargs)


class LogisticRegressionModel(BaseModel):
    """Logistic regression. Classification only."""

    def __init__(
        self,
        C: float = 1.0,
        penalty: str = "l2",
        random_state: int = 42,
        **kwargs: Any,
    ) -> None:
        super().__init__(task="classification", random_state=random_state)
        self.C = C
        self.penalty = penalty
        self.kwargs = kwargs

    def _build(self) -> Any:
        from sklearn.linear_model import LogisticRegression

        # The public kwarg stays `penalty` because that is what ml_tasks passes,
        # but scikit-learn 1.8 deprecated it in favour of l1_ratio. Translating
        # here keeps the caller's interface and avoids a DeprecationWarning per
        # fit -- which stability selection multiplies by its 100 bootstraps.
        params: dict[str, Any] = {
            "C": self.C,
            "random_state": self.random_state,
            "max_iter": 1000,
        }
        if self.penalty == "l1":
            params.update(l1_ratio=1.0, solver="saga")
        elif self.penalty in ("l2", None):
            params.update(l1_ratio=0.0)
        elif self.penalty == "elasticnet":
            params.update(l1_ratio=self.kwargs.pop("l1_ratio", 0.5), solver="saga")
        else:
            raise ValueError(f"Unsupported penalty {self.penalty!r}")

        return LogisticRegression(**params, **self.kwargs)


class ElasticNetModel(BaseModel):
    """Elastic net. Regression only."""

    def __init__(
        self,
        alpha: float = 1.0,
        l1_ratio: float = 0.5,
        random_state: int = 42,
        **kwargs: Any,
    ) -> None:
        super().__init__(task="regression", random_state=random_state)
        self.alpha = alpha
        self.l1_ratio = l1_ratio
        self.kwargs = kwargs

    def _build(self) -> Any:
        from sklearn.linear_model import ElasticNet

        return ElasticNet(
            alpha=self.alpha,
            l1_ratio=self.l1_ratio,
            random_state=self.random_state,
            max_iter=5000,
            **self.kwargs,
        )


__all__ = [
    "ElasticNetModel",
    "LightGBMModel",
    "LogisticRegressionModel",
    "RandomForestModel",
    "SVMModel",
    "XGBoostModel",
]

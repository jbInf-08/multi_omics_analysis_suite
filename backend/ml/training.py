"""Model Training Pipeline."""

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    r2_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import (
    KFold,
    StratifiedKFold,
    train_test_split,
)

from backend.ml.models.base import BaseModel, ModelMetrics

logger = logging.getLogger(__name__)


@dataclass
class TrainingConfig:
    """Training configuration."""

    test_size: float = 0.2
    cv_folds: int = 5
    stratify: bool = True
    random_state: int = 42
    early_stopping: bool = False
    early_stopping_rounds: int = 10


class ModelTrainer:
    """Model training and evaluation pipeline."""

    def __init__(self, config: TrainingConfig | None = None):
        self.config = config or TrainingConfig()
        self.best_model: BaseModel | None = None
        self.cv_results: dict | None = None
        self.test_results: dict | None = None

    def train(
        self,
        model: BaseModel,
        X: np.ndarray | pd.DataFrame,
        y: np.ndarray | pd.Series,
        X_val: np.ndarray | pd.DataFrame | None = None,
        y_val: np.ndarray | pd.Series | None = None,
    ) -> BaseModel:
        """Train a model.

        Args:
            model: Model to train
            X: Training features
            y: Training labels
            X_val: Validation features (optional)
            y_val: Validation labels (optional)

        Returns:
            Trained model

        """
        model.fit(X, y)
        return model

    def train_with_cv(
        self,
        model: BaseModel,
        X: np.ndarray | pd.DataFrame,
        y: np.ndarray | pd.Series,
    ) -> tuple[BaseModel, dict]:
        """Train with cross-validation.

        Args:
            model: Model to train
            X: Features
            y: Labels

        Returns:
            Tuple of (trained model, CV results)

        """
        X_arr = X.values if isinstance(X, pd.DataFrame) else X
        y_arr = y.values if isinstance(y, pd.Series) else y

        # Set up cross-validation
        if self.config.stratify and model.model_type == "classification":
            cv = StratifiedKFold(
                n_splits=self.config.cv_folds,
                shuffle=True,
                random_state=self.config.random_state,
            )
        else:
            cv = KFold(
                n_splits=self.config.cv_folds,
                shuffle=True,
                random_state=self.config.random_state,
            )

        # Collect fold results
        fold_metrics = []

        for _fold, (train_idx, val_idx) in enumerate(cv.split(X_arr, y_arr)):
            X_train, X_val = X_arr[train_idx], X_arr[val_idx]
            y_train, y_val = y_arr[train_idx], y_arr[val_idx]

            # Train on fold
            model.fit(X_train, y_train)

            # Evaluate
            y_pred = model.predict(X_val)

            if model.model_type == "classification":
                metrics = self._compute_classification_metrics(
                    y_val, y_pred, model.predict_proba(X_val)
                )
            else:
                metrics = self._compute_regression_metrics(y_val, y_pred)

            fold_metrics.append(metrics)

        # Aggregate results
        cv_results = self._aggregate_cv_results(fold_metrics)
        self.cv_results = cv_results

        # Train final model on all data
        model.fit(X_arr, y_arr)
        model.metrics = ModelMetrics(
            **{k: v["mean"] for k, v in cv_results.items() if isinstance(v, dict)}
        )

        self.best_model = model
        return model, cv_results

    def train_test_evaluate(
        self,
        model: BaseModel,
        X: np.ndarray | pd.DataFrame,
        y: np.ndarray | pd.Series,
    ) -> tuple[BaseModel, dict]:
        """Train on train set and evaluate on test set.

        Args:
            model: Model to train
            X: Features
            y: Labels

        Returns:
            Tuple of (trained model, test results)

        """
        X_arr = X.values if isinstance(X, pd.DataFrame) else X
        y_arr = y.values if isinstance(y, pd.Series) else y

        # Split data
        if self.config.stratify and model.model_type == "classification":
            X_train, X_test, y_train, y_test = train_test_split(
                X_arr,
                y_arr,
                test_size=self.config.test_size,
                random_state=self.config.random_state,
                stratify=y_arr,
            )
        else:
            X_train, X_test, y_train, y_test = train_test_split(
                X_arr,
                y_arr,
                test_size=self.config.test_size,
                random_state=self.config.random_state,
            )

        # Train
        model.fit(X_train, y_train)

        # Evaluate
        y_pred = model.predict(X_test)

        if model.model_type == "classification":
            y_proba = model.predict_proba(X_test)
            test_results = self._compute_classification_metrics(y_test, y_pred, y_proba)
        else:
            test_results = self._compute_regression_metrics(y_test, y_pred)

        model.metrics = ModelMetrics(**test_results)
        self.test_results = test_results
        self.best_model = model

        return model, test_results

    def _compute_classification_metrics(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        y_proba: np.ndarray | None = None,
    ) -> dict[str, float]:
        """Compute classification metrics."""
        metrics = {
            "accuracy": accuracy_score(y_true, y_pred),
            "precision": precision_score(y_true, y_pred, average="weighted", zero_division=0),
            "recall": recall_score(y_true, y_pred, average="weighted", zero_division=0),
            "f1": f1_score(y_true, y_pred, average="weighted", zero_division=0),
        }

        if y_proba is not None:
            try:
                if y_proba.shape[1] == 2:
                    metrics["auc_roc"] = roc_auc_score(y_true, y_proba[:, 1])
                    metrics["auc_pr"] = average_precision_score(y_true, y_proba[:, 1])
                else:
                    metrics["auc_roc"] = roc_auc_score(y_true, y_proba, multi_class="ovr")
            except Exception:
                logger.debug("optional metric could not be computed", exc_info=True)

        return metrics

    def _compute_regression_metrics(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
    ) -> dict[str, float]:
        """Compute regression metrics."""
        return {
            "mse": mean_squared_error(y_true, y_pred),
            "rmse": np.sqrt(mean_squared_error(y_true, y_pred)),
            "mae": mean_absolute_error(y_true, y_pred),
            "r2": r2_score(y_true, y_pred),
        }

    def _aggregate_cv_results(self, fold_metrics: list[dict]) -> dict:
        """Aggregate cross-validation results."""
        aggregated = {}

        for key in fold_metrics[0]:
            values = [m[key] for m in fold_metrics]
            aggregated[key] = {
                "mean": np.mean(values),
                "std": np.std(values),
                "values": values,
            }

        return aggregated

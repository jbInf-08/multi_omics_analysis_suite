"""Machine Learning Background Tasks.
=================================

Celery tasks for model training, AutoML, prediction, feature selection,
and model explanations using SHAP.
"""

import json
import logging
import traceback
import uuid as uuid_lib
from pathlib import Path
from typing import Any
from uuid import UUID

import numpy as np
import pandas as pd

from backend.app.core.celery_app import OmicsTask, celery_app

logger = logging.getLogger(__name__)


def get_sync_session():
    """Get a synchronous database session for Celery tasks."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from backend.app.core.config import settings

    sync_url = str(settings.DATABASE_URL).replace("+asyncpg", "")
    engine = create_engine(sync_url)
    Session = sessionmaker(bind=engine)
    return Session()


def load_dataset_data(dataset_id: str) -> pd.DataFrame | None:
    """Load dataset data from storage."""
    session = get_sync_session()
    try:
        from backend.app.models.dataset import Dataset

        dataset = session.query(Dataset).filter(Dataset.id == UUID(dataset_id)).first()
        if not dataset or not dataset.storage_path:
            logger.warning(f"Dataset {dataset_id} not found or has no storage path")
            return None

        storage_path = dataset.storage_path
        data_format = dataset.data_format or "csv"

        if data_format in ("csv", "tsv"):
            sep = "\t" if data_format == "tsv" else ","
            df = pd.read_csv(storage_path, sep=sep, index_col=0)
        elif data_format == "parquet":
            df = pd.read_parquet(storage_path)
        elif data_format == "feather":
            df = pd.read_feather(storage_path)
        else:
            df = pd.read_csv(storage_path, index_col=0)

        return df

    except Exception as e:
        logger.error(f"Failed to load dataset {dataset_id}: {e}")
        return None
    finally:
        session.close()


def get_model_storage_path(model_id: str) -> Path:
    """Get the storage path for a model."""
    from backend.app.core.config import settings

    base_path = Path(getattr(settings, "MODEL_STORAGE_PATH", "./models"))
    base_path.mkdir(parents=True, exist_ok=True)
    return base_path / model_id


@celery_app.task(base=OmicsTask, bind=True, name="train_model")
def train_model(
    self,
    model_type: str,
    dataset_ids: list[str],
    target_column: str,
    parameters: dict[str, Any] = None,
):
    """Train an ML model.

    Args:
        model_type: Type of model (random_forest, xgboost, lightgbm, svm, logistic, elastic_net)
        dataset_ids: Training dataset IDs
        target_column: Target variable column
        parameters: Model hyperparameters
            - test_size: float (default 0.2)
            - n_estimators: int (for tree models)
            - max_depth: int
            - learning_rate: float
            - C: float (for SVM/logistic)
            - task: str (classification or regression)

    Returns:
        Dict with model_id, metrics, and training details

    """
    parameters = parameters or {}
    model_id = str(uuid_lib.uuid4())

    try:
        self.update_state(state="PROGRESS", meta={"progress": 0.0, "step": "Loading data"})
        logger.info(f"Training {model_type} model")

        # Load and combine datasets
        all_data = []
        for i, dataset_id in enumerate(dataset_ids):
            df = load_dataset_data(dataset_id)
            if df is not None:
                all_data.append(df)

            progress = 0.1 * (i + 1) / len(dataset_ids)
            self.update_state(
                state="PROGRESS",
                meta={"progress": progress, "step": f"Loaded {i+1}/{len(dataset_ids)}"},
            )

        if not all_data:
            raise ValueError("No valid datasets loaded")

        # Combine data
        combined_df = pd.concat(all_data, axis=0) if len(all_data) > 1 else all_data[0]

        # Split features and target
        if target_column not in combined_df.columns:
            raise ValueError(f"Target column '{target_column}' not found in dataset")

        y = combined_df[target_column].values
        X = combined_df.drop(columns=[target_column]).values
        feature_names = [c for c in combined_df.columns if c != target_column]

        # Handle non-numeric targets
        label_encoder = None
        if not np.issubdtype(y.dtype, np.number):
            from sklearn.preprocessing import LabelEncoder

            label_encoder = LabelEncoder()
            y = label_encoder.fit_transform(y)

        self.update_state(state="PROGRESS", meta={"progress": 0.2, "step": "Preparing data"})

        # Train/test split
        from sklearn.model_selection import train_test_split

        test_size = parameters.get("test_size", 0.2)
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=parameters.get("random_state", 42)
        )

        # Scale features
        from sklearn.preprocessing import StandardScaler

        scaler = StandardScaler()
        X_train = scaler.fit_transform(X_train)
        X_test = scaler.transform(X_test)

        self.update_state(
            state="PROGRESS", meta={"progress": 0.3, "step": f"Training {model_type}"}
        )

        # Determine task type
        task = parameters.get("task")
        if task is None:
            unique_values = len(np.unique(y))
            task = "classification" if unique_values <= 20 else "regression"

        # Initialize and train model
        if model_type == "random_forest":
            from backend.ml.models.traditional import RandomForestModel

            model = RandomForestModel(
                n_estimators=parameters.get("n_estimators", 100),
                max_depth=parameters.get("max_depth"),
                task=task,
                random_state=parameters.get("random_state", 42),
            )
        elif model_type == "xgboost":
            from backend.ml.models.traditional import XGBoostModel

            model = XGBoostModel(
                n_estimators=parameters.get("n_estimators", 100),
                max_depth=parameters.get("max_depth", 6),
                learning_rate=parameters.get("learning_rate", 0.1),
                task=task,
                random_state=parameters.get("random_state", 42),
            )
        elif model_type == "lightgbm":
            from backend.ml.models.traditional import LightGBMModel

            model = LightGBMModel(
                n_estimators=parameters.get("n_estimators", 100),
                max_depth=parameters.get("max_depth", -1),
                learning_rate=parameters.get("learning_rate", 0.1),
                task=task,
                random_state=parameters.get("random_state", 42),
            )
        elif model_type == "svm":
            from backend.ml.models.traditional import SVMModel

            model = SVMModel(
                C=parameters.get("C", 1.0),
                kernel=parameters.get("kernel", "rbf"),
                task=task,
                random_state=parameters.get("random_state", 42),
            )
        elif model_type == "logistic":
            from backend.ml.models.traditional import LogisticRegressionModel

            model = LogisticRegressionModel(
                C=parameters.get("C", 1.0),
                penalty=parameters.get("penalty", "l2"),
                random_state=parameters.get("random_state", 42),
            )
        elif model_type == "elastic_net":
            from backend.ml.models.traditional import ElasticNetModel

            model = ElasticNetModel(
                alpha=parameters.get("alpha", 1.0),
                l1_ratio=parameters.get("l1_ratio", 0.5),
                random_state=parameters.get("random_state", 42),
            )
        else:
            raise ValueError(f"Unknown model type: {model_type}")

        # Train
        model.feature_names = feature_names
        model.fit(X_train, y_train)

        self.update_state(state="PROGRESS", meta={"progress": 0.7, "step": "Evaluating"})

        # Evaluate
        y_pred = model.predict(X_test)

        metrics = {}
        if task == "classification":
            from sklearn.metrics import (
                accuracy_score,
                f1_score,
                precision_score,
                recall_score,
                roc_auc_score,
            )

            metrics["accuracy"] = float(accuracy_score(y_test, y_pred))

            # Handle binary vs multiclass
            if len(np.unique(y)) == 2:
                metrics["precision"] = float(precision_score(y_test, y_pred, average="binary"))
                metrics["recall"] = float(recall_score(y_test, y_pred, average="binary"))
                metrics["f1"] = float(f1_score(y_test, y_pred, average="binary"))

                y_proba = model.predict_proba(X_test)
                if y_proba is not None:
                    metrics["auc_roc"] = float(roc_auc_score(y_test, y_proba[:, 1]))
            else:
                metrics["precision"] = float(precision_score(y_test, y_pred, average="weighted"))
                metrics["recall"] = float(recall_score(y_test, y_pred, average="weighted"))
                metrics["f1"] = float(f1_score(y_test, y_pred, average="weighted"))
        else:
            from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

            metrics["mse"] = float(mean_squared_error(y_test, y_pred))
            metrics["rmse"] = float(np.sqrt(metrics["mse"]))
            metrics["mae"] = float(mean_absolute_error(y_test, y_pred))
            metrics["r2"] = float(r2_score(y_test, y_pred))

        self.update_state(state="PROGRESS", meta={"progress": 0.9, "step": "Saving model"})

        # Save model
        model_path = get_model_storage_path(model_id)
        model.save(model_path)

        # Get feature importance
        feature_importance = model.get_feature_importance()
        top_features = None
        if feature_importance:
            sorted_features = sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)
            top_features = sorted_features[:20]

        self.update_state(state="PROGRESS", meta={"progress": 1.0, "step": "Complete"})

        logger.info(f"Model {model_id} trained successfully: {metrics}")

        return {
            "status": "completed",
            "model_type": model_type,
            "model_id": model_id,
            "task": task,
            "n_samples": X.shape[0],
            "n_features": X.shape[1],
            "test_size": test_size,
            "metrics": metrics,
            "top_features": top_features,
            "feature_names": feature_names[:100],  # Truncate
        }

    except Exception as e:
        logger.error(f"Model training failed: {e}\n{traceback.format_exc()}")
        return {
            "status": "failed",
            "model_type": model_type,
            "error": str(e),
        }


@celery_app.task(base=OmicsTask, bind=True, name="run_automl")
def run_automl(
    self,
    dataset_ids: list[str],
    target_column: str,
    task_type: str = "classification",
    time_budget: int = 3600,
    parameters: dict[str, Any] = None,
):
    """Run AutoML pipeline using Optuna for hyperparameter optimization.

    Args:
        dataset_ids: Training dataset IDs
        target_column: Target variable column
        task_type: Task type (classification, regression)
        time_budget: Time budget in seconds
        parameters: Additional parameters
            - n_trials: int (default 50)
            - cv_folds: int (default 5)
            - models: List[str] (models to try)

    Returns:
        Dict with best model, hyperparameters, and cross-validation results

    """
    parameters = parameters or {}
    str(uuid_lib.uuid4())

    try:
        import optuna
        from sklearn.model_selection import KFold, StratifiedKFold, cross_val_score

        self.update_state(state="PROGRESS", meta={"progress": 0.0, "step": "Starting AutoML"})
        logger.info(f"Running AutoML for {task_type}")

        # Load data
        all_data = []
        for dataset_id in dataset_ids:
            df = load_dataset_data(dataset_id)
            if df is not None:
                all_data.append(df)

        if not all_data:
            raise ValueError("No valid datasets loaded")

        combined_df = pd.concat(all_data, axis=0) if len(all_data) > 1 else all_data[0]

        y = combined_df[target_column].values
        X = combined_df.drop(columns=[target_column]).values
        [c for c in combined_df.columns if c != target_column]

        # Encode labels if classification
        label_encoder = None
        if task_type == "classification" and not np.issubdtype(y.dtype, np.number):
            from sklearn.preprocessing import LabelEncoder

            label_encoder = LabelEncoder()
            y = label_encoder.fit_transform(y)

        # Scale features
        from sklearn.preprocessing import StandardScaler

        scaler = StandardScaler()
        X = scaler.fit_transform(X)

        self.update_state(state="PROGRESS", meta={"progress": 0.1, "step": "Setting up trials"})

        # Cross-validation setup
        cv_folds = parameters.get("cv_folds", 5)
        if task_type == "classification":
            cv = StratifiedKFold(n_splits=cv_folds, shuffle=True, random_state=42)
            scoring = "f1_weighted" if len(np.unique(y)) > 2 else "f1"
        else:
            cv = KFold(n_splits=cv_folds, shuffle=True, random_state=42)
            scoring = "neg_mean_squared_error"

        models_to_try = parameters.get("models", ["random_forest", "xgboost", "lightgbm", "svm"])
        n_trials = parameters.get("n_trials", 50)

        {"score": float("-inf"), "model_type": None, "params": None}

        def objective(trial):
            model_type = trial.suggest_categorical("model_type", models_to_try)

            if model_type == "random_forest":
                from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor

                params = {
                    "n_estimators": trial.suggest_int("rf_n_estimators", 50, 300),
                    "max_depth": trial.suggest_int("rf_max_depth", 3, 20),
                    "min_samples_split": trial.suggest_int("rf_min_samples_split", 2, 20),
                    "random_state": 42,
                    "n_jobs": -1,
                }
                ModelClass = (
                    RandomForestClassifier
                    if task_type == "classification"
                    else RandomForestRegressor
                )
                model = ModelClass(**params)

            elif model_type == "xgboost":
                import xgboost as xgb

                params = {
                    "n_estimators": trial.suggest_int("xgb_n_estimators", 50, 300),
                    "max_depth": trial.suggest_int("xgb_max_depth", 3, 15),
                    "learning_rate": trial.suggest_float("xgb_learning_rate", 0.01, 0.3, log=True),
                    "subsample": trial.suggest_float("xgb_subsample", 0.6, 1.0),
                    "random_state": 42,
                }
                if task_type == "classification":
                    params["use_label_encoder"] = False
                    params["eval_metric"] = "logloss"
                    model = xgb.XGBClassifier(**params)
                else:
                    model = xgb.XGBRegressor(**params)

            elif model_type == "lightgbm":
                import lightgbm as lgb

                params = {
                    "n_estimators": trial.suggest_int("lgb_n_estimators", 50, 300),
                    "max_depth": trial.suggest_int("lgb_max_depth", 3, 15),
                    "learning_rate": trial.suggest_float("lgb_learning_rate", 0.01, 0.3, log=True),
                    "num_leaves": trial.suggest_int("lgb_num_leaves", 10, 100),
                    "random_state": 42,
                    "verbose": -1,
                }
                ModelClass = (
                    lgb.LGBMClassifier if task_type == "classification" else lgb.LGBMRegressor
                )
                model = ModelClass(**params)

            elif model_type == "svm":
                from sklearn.svm import SVC, SVR

                params = {
                    "C": trial.suggest_float("svm_C", 0.01, 100, log=True),
                    "kernel": trial.suggest_categorical("svm_kernel", ["rbf", "linear"]),
                    "random_state": 42,
                }
                model = SVC(**params) if task_type == "classification" else SVR(**params)
            else:
                raise ValueError(f"Unknown model: {model_type}")

            scores = cross_val_score(model, X, y, cv=cv, scoring=scoring, n_jobs=-1)
            return scores.mean()

        # Run optimization
        optuna.logging.set_verbosity(optuna.logging.WARNING)
        study = optuna.create_study(direction="maximize")

        trials_completed = [0]

        def callback(study, trial):
            trials_completed[0] += 1
            progress = 0.1 + 0.7 * (trials_completed[0] / n_trials)
            self.update_state(
                state="PROGRESS",
                meta={"progress": progress, "step": f"Trial {trials_completed[0]}/{n_trials}"},
            )

        study.optimize(objective, n_trials=n_trials, timeout=time_budget, callbacks=[callback])

        self.update_state(state="PROGRESS", meta={"progress": 0.85, "step": "Training best model"})

        # Get best parameters
        best_params = study.best_params
        best_model_type = best_params.pop("model_type")

        # Clean parameter names
        clean_params = {}
        for k, v in best_params.items():
            clean_key = k.split("_", 1)[1] if "_" in k else k
            clean_params[clean_key] = v

        # Train final model with best parameters
        final_result = train_model(
            model_type=best_model_type,
            dataset_ids=dataset_ids,
            target_column=target_column,
            parameters={**clean_params, "task": task_type},
        )

        self.update_state(state="PROGRESS", meta={"progress": 1.0, "step": "Complete"})

        logger.info(f"AutoML completed: best model={best_model_type}, score={study.best_value:.4f}")

        return {
            "status": "completed",
            "task_type": task_type,
            "best_model_type": best_model_type,
            "best_model_id": final_result.get("model_id"),
            "best_score": float(study.best_value),
            "best_params": clean_params,
            "n_trials": len(study.trials),
            "final_metrics": final_result.get("metrics"),
            "top_features": final_result.get("top_features"),
        }

    except Exception as e:
        logger.error(f"AutoML failed: {e}\n{traceback.format_exc()}")
        return {
            "status": "failed",
            "task_type": task_type,
            "error": str(e),
        }


@celery_app.task(base=OmicsTask, name="run_prediction")
def run_prediction(
    model_id: str,
    dataset_id: str,
    parameters: dict[str, Any] = None,
):
    """Run prediction using a trained model.

    Args:
        model_id: Trained model ID
        dataset_id: Dataset to predict on
        parameters: Prediction parameters
            - return_probabilities: bool (default True for classifiers)
            - batch_size: int (for large datasets)

    Returns:
        Dict with predictions and optionally probabilities

    """
    parameters = parameters or {}

    try:
        logger.info(f"Running prediction with model {model_id}")

        # Load model
        model_path = get_model_storage_path(model_id)
        model_file = model_path.with_suffix(".joblib")
        metadata_file = model_path.with_suffix(".json")

        if not model_file.exists():
            raise ValueError(f"Model {model_id} not found")

        import joblib

        model = joblib.load(model_file)

        with open(metadata_file) as f:
            metadata = json.load(f)

        # Load dataset
        df = load_dataset_data(dataset_id)
        if df is None:
            raise ValueError(f"Dataset {dataset_id} not found")

        # Get feature names from metadata
        feature_names = metadata.get("feature_names", [])

        # Ensure columns match
        if feature_names:
            missing_cols = set(feature_names) - set(df.columns)
            if missing_cols:
                logger.warning(f"Missing columns: {missing_cols}")
            available_cols = [c for c in feature_names if c in df.columns]
            X = df[available_cols].values
        else:
            X = df.values

        # Scale features
        from sklearn.preprocessing import StandardScaler

        scaler = StandardScaler()
        X = scaler.fit_transform(X)  # Note: ideally should use saved scaler

        # Predict
        predictions = model.predict(X)

        result = {
            "status": "completed",
            "model_id": model_id,
            "dataset_id": dataset_id,
            "n_samples": len(predictions),
            "predictions": predictions.tolist()[:1000],  # Truncate for response
            "sample_names": df.index.tolist()[:1000],
        }

        # Get probabilities for classifiers
        if parameters.get("return_probabilities", True) and hasattr(model, "predict_proba"):
            try:
                probabilities = model.predict_proba(X)
                result["probabilities"] = probabilities.tolist()[:1000]
                if hasattr(model, "classes_"):
                    result["classes"] = model.classes_.tolist()
            except Exception:
                logger.debug("prediction probabilities unavailable", exc_info=True)

        logger.info(f"Prediction completed: {len(predictions)} samples")

        return result

    except Exception as e:
        logger.error(f"Prediction failed: {e}\n{traceback.format_exc()}")
        return {
            "status": "failed",
            "model_id": model_id,
            "error": str(e),
        }


@celery_app.task(base=OmicsTask, bind=True, name="run_feature_selection")
def run_feature_selection(
    self,
    dataset_id: str,
    method: str,
    n_features: int = None,
    target_column: str = None,
    parameters: dict[str, Any] = None,
):
    """Run feature selection.

    Args:
        dataset_id: Dataset ID
        method: Selection method (variance, mutual_info, f_classif, chi2, rfe, lasso, random_forest)
        n_features: Number of features to select
        target_column: Target column for supervised methods
        parameters: Method-specific parameters
            - threshold: float (for variance)
            - alpha: float (for lasso)
            - n_estimators: int (for tree-based methods)

    Returns:
        Dict with selected features and their scores

    """
    parameters = parameters or {}
    n_features = n_features or 50

    try:
        self.update_state(state="PROGRESS", meta={"progress": 0.0, "step": "Loading data"})
        logger.info(f"Running {method} feature selection")

        # Load dataset
        df = load_dataset_data(dataset_id)
        if df is None:
            raise ValueError(f"Dataset {dataset_id} not found")

        # Separate target if supervised
        y = None
        if target_column and target_column in df.columns:
            y = df[target_column].values
            X = df.drop(columns=[target_column])

            # Encode categorical target
            if not np.issubdtype(y.dtype, np.number):
                from sklearn.preprocessing import LabelEncoder

                le = LabelEncoder()
                y = le.fit_transform(y)
        else:
            X = df

        feature_names = X.columns.tolist()
        X = X.values

        # Scale features
        from sklearn.preprocessing import StandardScaler

        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        self.update_state(state="PROGRESS", meta={"progress": 0.3, "step": f"Running {method}"})

        selected_indices = None
        scores = None

        if method == "variance":
            from sklearn.feature_selection import VarianceThreshold

            threshold = parameters.get("threshold", 0.0)
            selector = VarianceThreshold(threshold=threshold)
            selector.fit(X_scaled)
            scores = selector.variances_
            selected_indices = np.argsort(scores)[-n_features:]

        elif method == "mutual_info":
            if y is None:
                raise ValueError("Target column required for mutual_info")
            from sklearn.feature_selection import mutual_info_classif

            scores = mutual_info_classif(X_scaled, y, random_state=42)
            selected_indices = np.argsort(scores)[-n_features:]

        elif method == "f_classif":
            if y is None:
                raise ValueError("Target column required for f_classif")
            from sklearn.feature_selection import f_classif

            scores, _ = f_classif(X_scaled, y)
            scores = np.nan_to_num(scores, nan=0.0)
            selected_indices = np.argsort(scores)[-n_features:]

        elif method == "chi2":
            if y is None:
                raise ValueError("Target column required for chi2")
            from sklearn.feature_selection import chi2

            # Chi2 requires non-negative features
            X_pos = X - X.min(axis=0)
            scores, _ = chi2(X_pos, y)
            scores = np.nan_to_num(scores, nan=0.0)
            selected_indices = np.argsort(scores)[-n_features:]

        elif method == "rfe":
            if y is None:
                raise ValueError("Target column required for RFE")
            from sklearn.ensemble import RandomForestClassifier
            from sklearn.feature_selection import RFE

            base_model = RandomForestClassifier(
                n_estimators=parameters.get("n_estimators", 50),
                random_state=42,
                n_jobs=-1,
            )
            selector = RFE(base_model, n_features_to_select=n_features)
            selector.fit(X_scaled, y)
            selected_indices = np.where(selector.support_)[0]
            scores = 1.0 / selector.ranking_  # Convert ranking to scores

        elif method == "lasso":
            from sklearn.linear_model import LassoCV

            alpha = parameters.get("alpha")

            if alpha:
                from sklearn.linear_model import Lasso

                model = Lasso(alpha=alpha, random_state=42, max_iter=5000)
            else:
                model = LassoCV(cv=5, random_state=42, max_iter=5000)

            if y is not None:
                model.fit(X_scaled, y.astype(float))
            else:
                # Use mean of all columns as pseudo-target
                model.fit(X_scaled, X_scaled.mean(axis=1))

            scores = np.abs(model.coef_)
            selected_indices = np.argsort(scores)[-n_features:]

        elif method == "random_forest":
            if y is None:
                raise ValueError("Target column required for random_forest")
            from sklearn.ensemble import RandomForestClassifier

            model = RandomForestClassifier(
                n_estimators=parameters.get("n_estimators", 100),
                random_state=42,
                n_jobs=-1,
            )
            model.fit(X_scaled, y)
            scores = model.feature_importances_
            selected_indices = np.argsort(scores)[-n_features:]

        else:
            raise ValueError(f"Unknown feature selection method: {method}")

        self.update_state(state="PROGRESS", meta={"progress": 0.8, "step": "Compiling results"})

        # Format results
        selected_features = []
        for idx in sorted(selected_indices, key=lambda i: scores[i], reverse=True):
            selected_features.append(
                {
                    "feature": feature_names[idx],
                    "score": float(scores[idx]),
                    "rank": len(selected_features) + 1,
                }
            )

        self.update_state(state="PROGRESS", meta={"progress": 1.0, "step": "Complete"})

        logger.info(f"Feature selection completed: {len(selected_features)} features selected")

        return {
            "status": "completed",
            "method": method,
            "n_features": len(selected_features),
            "n_original_features": len(feature_names),
            "selected_features": selected_features,
        }

    except Exception as e:
        logger.error(f"Feature selection failed: {e}\n{traceback.format_exc()}")
        return {
            "status": "failed",
            "method": method,
            "error": str(e),
        }


@celery_app.task(base=OmicsTask, bind=True, name="generate_shap_explanations")
def generate_shap_explanations(
    self,
    model_id: str,
    dataset_id: str,
    sample_ids: list[str] = None,
    n_samples: int = 100,
    n_background: int = 50,
):
    """Generate SHAP explanations for a model.

    Args:
        model_id: Model ID
        dataset_id: Dataset ID
        sample_ids: Specific samples to explain (if None, explains all)
        n_samples: Max number of samples to explain
        n_background: Number of background samples for SHAP

    Returns:
        Dict with SHAP values, feature importance, and summary statistics

    """
    try:
        import shap

        self.update_state(state="PROGRESS", meta={"progress": 0.0, "step": "Loading model"})
        logger.info(f"Generating SHAP explanations for model {model_id}")

        # Load model
        model_path = get_model_storage_path(model_id)
        model_file = model_path.with_suffix(".joblib")
        metadata_file = model_path.with_suffix(".json")

        if not model_file.exists():
            raise ValueError(f"Model {model_id} not found")

        import joblib

        model = joblib.load(model_file)

        with open(metadata_file) as f:
            metadata = json.load(f)

        feature_names = metadata.get("feature_names", [])

        self.update_state(state="PROGRESS", meta={"progress": 0.1, "step": "Loading data"})

        # Load dataset
        df = load_dataset_data(dataset_id)
        if df is None:
            raise ValueError(f"Dataset {dataset_id} not found")

        # Filter to matching columns
        if feature_names:
            available_cols = [c for c in feature_names if c in df.columns]
            X = df[available_cols]
        else:
            X = df
            feature_names = X.columns.tolist()

        # Filter to specific samples
        if sample_ids:
            X = X.loc[X.index.isin(sample_ids)]

        # Limit samples
        if len(X) > n_samples:
            X = X.sample(n=n_samples, random_state=42)

        sample_names = X.index.tolist()
        X_values = X.values

        # Scale features
        from sklearn.preprocessing import StandardScaler

        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X_values)

        self.update_state(state="PROGRESS", meta={"progress": 0.3, "step": "Creating explainer"})

        # Select background samples
        background_size = min(n_background, len(X_scaled))
        background_indices = np.random.choice(len(X_scaled), background_size, replace=False)
        background = X_scaled[background_indices]

        # Create SHAP explainer based on model type
        model_type = metadata.get("model_type", "generic")

        if model_type in ("random_forest", "xgboost", "lightgbm"):
            # Tree explainer is faster for tree-based models
            try:
                explainer = shap.TreeExplainer(model)
            except Exception:
                logger.debug(
                    "TreeExplainer unavailable; falling back to KernelExplainer", exc_info=True
                )
                explainer = shap.KernelExplainer(model.predict, background)
        else:
            # Kernel explainer for other models
            if hasattr(model, "predict_proba"):
                explainer = shap.KernelExplainer(model.predict_proba, background)
            else:
                explainer = shap.KernelExplainer(model.predict, background)

        self.update_state(state="PROGRESS", meta={"progress": 0.5, "step": "Computing SHAP values"})

        # Compute SHAP values
        shap_values = explainer.shap_values(X_scaled)

        # Handle multi-class output
        if isinstance(shap_values, list):
            # For multi-class, use absolute mean across classes
            shap_values = np.abs(np.array(shap_values)).mean(axis=0)

        self.update_state(state="PROGRESS", meta={"progress": 0.8, "step": "Computing importance"})

        # Compute global feature importance
        global_importance = np.abs(shap_values).mean(axis=0)
        importance_ranking = np.argsort(global_importance)[::-1]

        # Top features
        top_features = []
        for i, idx in enumerate(importance_ranking[:20]):
            top_features.append(
                {
                    "rank": i + 1,
                    "feature": feature_names[idx] if idx < len(feature_names) else f"feature_{idx}",
                    "importance": float(global_importance[idx]),
                    "mean_shap": float(np.mean(shap_values[:, idx])),
                    "std_shap": float(np.std(shap_values[:, idx])),
                }
            )

        # Sample-level explanations (top 10 samples)
        sample_explanations = []
        for i, sample_name in enumerate(sample_names[:10]):
            sample_shap = shap_values[i]
            top_indices = np.argsort(np.abs(sample_shap))[-5:][::-1]

            sample_explanations.append(
                {
                    "sample": sample_name,
                    "top_contributors": [
                        {
                            "feature": (
                                feature_names[idx] if idx < len(feature_names) else f"feature_{idx}"
                            ),
                            "shap_value": float(sample_shap[idx]),
                        }
                        for idx in top_indices
                    ],
                }
            )

        self.update_state(state="PROGRESS", meta={"progress": 1.0, "step": "Complete"})

        logger.info(f"SHAP explanations generated for {len(sample_names)} samples")

        return {
            "status": "completed",
            "model_id": model_id,
            "dataset_id": dataset_id,
            "n_samples_explained": len(sample_names),
            "n_features": len(feature_names),
            "top_features": top_features,
            "sample_explanations": sample_explanations,
            "expected_value": (
                float(explainer.expected_value)
                if hasattr(explainer, "expected_value")
                and not isinstance(explainer.expected_value, list)
                else None
            ),
        }

    except ImportError:
        return {
            "status": "failed",
            "model_id": model_id,
            "error": "SHAP not installed. Install with: pip install shap",
        }
    except Exception as e:
        logger.error(f"SHAP explanations failed: {e}\n{traceback.format_exc()}")
        return {
            "status": "failed",
            "model_id": model_id,
            "error": str(e),
        }


@celery_app.task(base=OmicsTask, bind=True, name="train_gnn_model")
def train_gnn_model(
    self,
    dataset_id: str,
    graph_type: str,
    model_config: dict[str, Any],
    training_params: dict[str, Any] = None,
    target_column: str = None,
):
    """Train a Graph Neural Network model.

    Args:
        dataset_id: Dataset ID
        graph_type: Type of graph (ppi, coexpression, knn, full)
        model_config: GNN model configuration
            - model_type: str (gcn, gat, graphsage)
            - hidden_channels: int (default 64)
            - num_layers: int (default 2)
            - dropout: float (default 0.5)
        training_params: Training parameters
            - epochs: int (default 200)
            - lr: float (default 0.01)
            - weight_decay: float (default 5e-4)
            - patience: int (default 20)
        target_column: Target column for node classification

    Returns:
        Dict with model performance and training history

    """
    model_config = model_config or {}
    training_params = training_params or {}
    model_id = str(uuid_lib.uuid4())

    try:
        self.update_state(state="PROGRESS", meta={"progress": 0.0, "step": "Loading data"})
        logger.info(f"Training GNN model with graph_type={graph_type}")

        # Load dataset
        df = load_dataset_data(dataset_id)
        if df is None:
            raise ValueError(f"Dataset {dataset_id} not found")

        # Separate features and target
        if target_column and target_column in df.columns:
            y = df[target_column].values
            X = df.drop(columns=[target_column]).values

            # Encode labels
            from sklearn.preprocessing import LabelEncoder

            le = LabelEncoder()
            y = le.fit_transform(y)
            n_classes = len(le.classes_)
        else:
            X = df.values
            y = None
            n_classes = None

        feature_names = [c for c in df.columns if c != target_column]
        n_nodes = X.shape[0]
        n_features = X.shape[1]

        self.update_state(state="PROGRESS", meta={"progress": 0.1, "step": "Building graph"})

        # Build adjacency matrix based on graph type
        from backend.omics.base.omics_base import OmicsData
        from backend.omics.integration.network_integration import NetworkIntegrator

        omics_data = OmicsData(
            data=pd.DataFrame(X, columns=feature_names),
            sample_names=[f"node_{i}" for i in range(n_nodes)],
            feature_names=feature_names,
            omics_type="generic",
        )

        if graph_type == "coexpression":
            threshold = model_config.get("correlation_threshold", 0.7)
            adj = NetworkIntegrator.build_coexpression_network(
                omics_data,
                method="pearson",
                threshold=threshold,
            )
        elif graph_type == "knn":
            k = model_config.get("k_neighbors", 10)
            adj = NetworkIntegrator.build_sample_network(
                omics_data,
                metric="euclidean",
                k_neighbors=k,
            )
        elif graph_type == "full":
            adj = np.ones((n_nodes, n_nodes)) - np.eye(n_nodes)
        else:
            # Default to KNN
            adj = NetworkIntegrator.build_sample_network(
                omics_data,
                metric="euclidean",
                k_neighbors=10,
            )

        # Convert to edge index
        edge_sources, edge_targets = np.where(adj > 0)
        n_edges = len(edge_sources)

        self.update_state(
            state="PROGRESS", meta={"progress": 0.2, "step": "Preparing PyTorch data"}
        )

        try:
            import torch
            import torch.nn.functional as F
            from torch_geometric.data import Data
            from torch_geometric.nn import GATConv, GCNConv, SAGEConv
        except ImportError:
            return {
                "status": "failed",
                "error": "PyTorch Geometric not installed. Install with: pip install torch-geometric",
            }

        # Create PyTorch Geometric data
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        x = torch.FloatTensor(X).to(device)
        edge_index = torch.LongTensor([edge_sources, edge_targets]).to(device)

        if y is not None:
            y = torch.LongTensor(y).to(device)

        data = Data(x=x, edge_index=edge_index, y=y)

        # Create train/val/test masks
        if y is not None:
            n_train = int(0.6 * n_nodes)
            n_val = int(0.2 * n_nodes)

            perm = torch.randperm(n_nodes)
            train_mask = torch.zeros(n_nodes, dtype=torch.bool)
            val_mask = torch.zeros(n_nodes, dtype=torch.bool)
            test_mask = torch.zeros(n_nodes, dtype=torch.bool)

            train_mask[perm[:n_train]] = True
            val_mask[perm[n_train : n_train + n_val]] = True
            test_mask[perm[n_train + n_val :]] = True

            data.train_mask = train_mask.to(device)
            data.val_mask = val_mask.to(device)
            data.test_mask = test_mask.to(device)

        self.update_state(state="PROGRESS", meta={"progress": 0.3, "step": "Building model"})

        # Build GNN model
        model_type = model_config.get("model_type", "gcn")
        hidden_channels = model_config.get("hidden_channels", 64)
        num_layers = model_config.get("num_layers", 2)
        dropout = model_config.get("dropout", 0.5)

        class GNN(torch.nn.Module):
            def __init__(
                self, in_channels, hidden_channels, out_channels, num_layers, dropout, conv_type
            ):
                super().__init__()
                self.convs = torch.nn.ModuleList()
                self.dropout = dropout

                # Select convolution type
                if conv_type == "gcn":
                    Conv = GCNConv
                elif conv_type == "gat":

                    def Conv(in_c, out_c):
                        return GATConv(in_c, out_c, heads=4, concat=False)

                elif conv_type == "graphsage":
                    Conv = SAGEConv
                else:
                    Conv = GCNConv

                # Build layers
                self.convs.append(Conv(in_channels, hidden_channels))
                for _ in range(num_layers - 2):
                    self.convs.append(Conv(hidden_channels, hidden_channels))
                self.convs.append(Conv(hidden_channels, out_channels))

            def forward(self, x, edge_index):
                for _i, conv in enumerate(self.convs[:-1]):
                    x = conv(x, edge_index)
                    x = F.relu(x)
                    x = F.dropout(x, p=self.dropout, training=self.training)
                x = self.convs[-1](x, edge_index)
                return x

        out_channels = n_classes if n_classes else hidden_channels
        gnn_model = GNN(
            n_features, hidden_channels, out_channels, num_layers, dropout, model_type
        ).to(device)

        # Training setup
        epochs = training_params.get("epochs", 200)
        lr = training_params.get("lr", 0.01)
        weight_decay = training_params.get("weight_decay", 5e-4)
        patience = training_params.get("patience", 20)

        optimizer = torch.optim.Adam(gnn_model.parameters(), lr=lr, weight_decay=weight_decay)

        self.update_state(state="PROGRESS", meta={"progress": 0.4, "step": "Training"})

        # Training loop
        history = {"train_loss": [], "val_loss": [], "val_acc": []}
        best_val_loss = float("inf")
        patience_counter = 0

        for epoch in range(epochs):
            gnn_model.train()
            optimizer.zero_grad()
            out = gnn_model(data.x, data.edge_index)

            if y is not None:
                loss = F.cross_entropy(out[data.train_mask], data.y[data.train_mask])
                loss.backward()
                optimizer.step()

                # Validation
                gnn_model.eval()
                with torch.no_grad():
                    out = gnn_model(data.x, data.edge_index)
                    val_loss = F.cross_entropy(out[data.val_mask], data.y[data.val_mask]).item()
                    pred = out[data.val_mask].argmax(dim=1)
                    val_acc = (pred == data.y[data.val_mask]).float().mean().item()

                history["train_loss"].append(loss.item())
                history["val_loss"].append(val_loss)
                history["val_acc"].append(val_acc)

                # Early stopping
                if val_loss < best_val_loss:
                    best_val_loss = val_loss
                    patience_counter = 0
                    best_model_state = gnn_model.state_dict().copy()
                else:
                    patience_counter += 1
                    if patience_counter >= patience:
                        logger.info(f"Early stopping at epoch {epoch}")
                        break
            else:
                # Unsupervised - just run forward pass
                loss = (out**2).mean()
                loss.backward()
                optimizer.step()
                history["train_loss"].append(loss.item())

            if (epoch + 1) % 20 == 0:
                progress = 0.4 + 0.5 * (epoch + 1) / epochs
                self.update_state(
                    state="PROGRESS",
                    meta={"progress": progress, "step": f"Epoch {epoch+1}/{epochs}"},
                )

        self.update_state(state="PROGRESS", meta={"progress": 0.95, "step": "Evaluating"})

        # Final evaluation
        metrics = {}
        if y is not None and hasattr(data, "test_mask"):
            gnn_model.load_state_dict(best_model_state)
            gnn_model.eval()
            with torch.no_grad():
                out = gnn_model(data.x, data.edge_index)
                pred = out[data.test_mask].argmax(dim=1)
                test_acc = (pred == data.y[data.test_mask]).float().mean().item()
                metrics["test_accuracy"] = test_acc
                metrics["best_val_accuracy"] = (
                    max(history["val_acc"]) if history["val_acc"] else None
                )

        # Save model
        model_path = get_model_storage_path(model_id)
        torch.save(
            {
                "model_state_dict": gnn_model.state_dict(),
                "model_config": model_config,
                "n_features": n_features,
                "n_classes": n_classes,
            },
            model_path.with_suffix(".pt"),
        )

        self.update_state(state="PROGRESS", meta={"progress": 1.0, "step": "Complete"})

        logger.info(f"GNN training completed: {metrics}")

        return {
            "status": "completed",
            "model_id": model_id,
            "graph_type": graph_type,
            "model_type": model_type,
            "n_nodes": n_nodes,
            "n_edges": n_edges,
            "n_features": n_features,
            "n_classes": n_classes,
            "epochs_trained": len(history["train_loss"]),
            "metrics": metrics,
            "final_train_loss": history["train_loss"][-1] if history["train_loss"] else None,
        }

    except Exception as e:
        logger.error(f"GNN training failed: {e}\n{traceback.format_exc()}")
        return {
            "status": "failed",
            "graph_type": graph_type,
            "error": str(e),
        }

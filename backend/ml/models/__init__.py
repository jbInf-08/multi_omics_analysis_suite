"""Model registry for the ML engine.

Reconstructed from call sites -- see the note in base.py. The names here are
fixed by backend/ml/automl.py, whose search space is keyed on
random_forest, xgboost, lightgbm, svm and elastic_net, and by
backend/app/tasks/ml_tasks.py, which additionally builds logistic.
"""

from __future__ import annotations

from typing import Any

from backend.ml.models.base import BaseModel, ModelMetrics
from backend.ml.models.traditional import (
    ElasticNetModel,
    LightGBMModel,
    LogisticRegressionModel,
    RandomForestModel,
    SVMModel,
    XGBoostModel,
)

#: Registry name -> class. Keys match automl's model_space and the branches in
#: ml_tasks, so a name valid in one is valid in the other.
_REGISTRY: dict[str, type[BaseModel]] = {
    "random_forest": RandomForestModel,
    "xgboost": XGBoostModel,
    "lightgbm": LightGBMModel,
    "svm": SVMModel,
    "logistic": LogisticRegressionModel,
    "elastic_net": ElasticNetModel,
}

#: Which task each model can serve. Used to reject a mismatch up front rather
#: than let it surface as an obscure estimator error during fit.
_TASKS: dict[str, tuple[str, ...]] = {
    "random_forest": ("classification", "regression"),
    "xgboost": ("classification", "regression"),
    "lightgbm": ("classification", "regression"),
    "svm": ("classification", "regression"),
    "logistic": ("classification",),
    "elastic_net": ("regression",),
}


def get_model(name: str, **params: Any) -> BaseModel:
    """Build a model by registry name.

    Args:
        name: One of :func:`list_available_models`.
        **params: Forwarded to the model's constructor.

    Raises:
        ValueError: If the name is unknown, or the requested task is one the
            model cannot serve.

    """
    key = str(name).lower()
    if key not in _REGISTRY:
        raise ValueError(f"Unknown model {name!r}. Available: {sorted(_REGISTRY)}")

    task = params.get("task")
    if task is not None and task not in _TASKS[key]:
        raise ValueError(
            f"Model {key!r} does not support task {task!r}; it supports {list(_TASKS[key])}"
        )

    cls = _REGISTRY[key]
    # logistic and elastic_net fix their own task, so passing it through would
    # be a duplicate keyword.
    if key in ("logistic", "elastic_net"):
        params.pop("task", None)
    return cls(**params)


def list_available_models() -> list[dict[str, Any]]:
    """Registry contents, for the /ml/models endpoint."""
    return [
        {
            "name": name,
            "class": cls.__name__,
            "tasks": list(_TASKS[name]),
        }
        for name, cls in sorted(_REGISTRY.items())
    ]


__all__ = [
    "BaseModel",
    "ElasticNetModel",
    "LightGBMModel",
    "LogisticRegressionModel",
    "ModelMetrics",
    "RandomForestModel",
    "SVMModel",
    "XGBoostModel",
    "get_model",
    "list_available_models",
]

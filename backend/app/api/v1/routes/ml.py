"""
Machine Learning Routes
"""

from typing import List, Optional, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field

from backend.app.core.security import get_current_user, TokenPayload


router = APIRouter()


class ModelInfo(BaseModel):
    """ML Model information."""
    name: str
    model_type: str
    description: str
    supported_omics: List[str]
    parameters: Dict[str, Any]
    metrics: Optional[Dict[str, float]] = None


class TrainRequest(BaseModel):
    """Model training request."""
    model_type: str
    dataset_ids: List[UUID]
    target_column: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    cross_validation: bool = True
    cv_folds: int = 5
    test_size: float = 0.2


class PredictRequest(BaseModel):
    """Model prediction request."""
    model_id: UUID
    dataset_id: UUID
    parameters: Dict[str, Any] = Field(default_factory=dict)


class FeatureSelectionRequest(BaseModel):
    """Feature selection request."""
    dataset_id: UUID
    method: str  # filter, wrapper, embedded
    parameters: Dict[str, Any] = Field(default_factory=dict)
    n_features: Optional[int] = None


class ExplainRequest(BaseModel):
    """Model explanation request."""
    model_id: UUID
    method: str  # shap, lime
    sample_ids: Optional[List[str]] = None
    n_samples: int = 100


@router.get("/models", response_model=List[ModelInfo])
async def list_available_models(
    model_type: Optional[str] = None,
    omics_type: Optional[str] = None,
    current_user: TokenPayload = Depends(get_current_user),
):
    """List available ML models."""
    # Define available models
    models = [
        ModelInfo(
            name="Random Forest Classifier",
            model_type="classification",
            description="Ensemble classifier using multiple decision trees",
            supported_omics=["genomics", "transcriptomics", "proteomics", "metabolomics"],
            parameters={"n_estimators": 100, "max_depth": None, "min_samples_split": 2},
        ),
        ModelInfo(
            name="XGBoost Classifier",
            model_type="classification",
            description="Gradient boosting classifier with regularization",
            supported_omics=["genomics", "transcriptomics", "proteomics", "metabolomics"],
            parameters={"n_estimators": 100, "learning_rate": 0.1, "max_depth": 6},
        ),
        ModelInfo(
            name="Logistic Regression",
            model_type="classification",
            description="Linear classifier with L1/L2 regularization",
            supported_omics=["genomics", "transcriptomics", "proteomics", "metabolomics"],
            parameters={"penalty": "l2", "C": 1.0, "max_iter": 1000},
        ),
        ModelInfo(
            name="SVM Classifier",
            model_type="classification",
            description="Support Vector Machine classifier",
            supported_omics=["genomics", "transcriptomics", "proteomics"],
            parameters={"kernel": "rbf", "C": 1.0, "gamma": "scale"},
        ),
        ModelInfo(
            name="Neural Network",
            model_type="classification",
            description="Multi-layer perceptron classifier",
            supported_omics=["genomics", "transcriptomics", "proteomics", "metabolomics"],
            parameters={"hidden_layers": [256, 128, 64], "dropout": 0.3, "learning_rate": 0.001},
        ),
        ModelInfo(
            name="Graph Attention Network",
            model_type="classification",
            description="GNN with attention mechanism for biological networks",
            supported_omics=["genomics", "interactomics", "regulomics"],
            parameters={"heads": 8, "hidden_dim": 64, "num_layers": 3},
        ),
        ModelInfo(
            name="Genomic Transformer",
            model_type="classification",
            description="Transformer model for genomic sequences",
            supported_omics=["genomics", "transcriptomics"],
            parameters={"d_model": 256, "nhead": 8, "num_layers": 6},
        ),
        ModelInfo(
            name="Cox Proportional Hazards",
            model_type="survival",
            description="Survival analysis model",
            supported_omics=["genomics", "transcriptomics", "proteomics"],
            parameters={"penalizer": 0.1, "l1_ratio": 0.5},
        ),
        ModelInfo(
            name="DeepSurv",
            model_type="survival",
            description="Deep learning survival model",
            supported_omics=["genomics", "transcriptomics", "proteomics"],
            parameters={"hidden_layers": [128, 64], "dropout": 0.2},
        ),
    ]
    
    # Filter by type
    if model_type:
        models = [m for m in models if m.model_type == model_type]
    
    # Filter by omics
    if omics_type:
        models = [m for m in models if omics_type in m.supported_omics]
    
    return models


@router.post("/train")
async def train_model(
    request: TrainRequest,
    current_user: TokenPayload = Depends(get_current_user),
):
    """Train a new ML model."""
    from backend.app.tasks.ml_tasks import train_model as train_model_task
    
    # Map model type names
    model_type_map = {
        "random_forest": "random_forest",
        "xgboost": "xgboost",
        "lightgbm": "lightgbm",
        "logistic_regression": "logistic",
        "logistic": "logistic",
        "svm": "svm",
        "elastic_net": "elastic_net",
    }
    
    model_type = model_type_map.get(request.model_type.lower(), request.model_type)
    
    # Start training task
    task = train_model_task.delay(
        model_type=model_type,
        dataset_ids=[str(d) for d in request.dataset_ids],
        target_column=request.target_column,
        parameters={
            **request.parameters,
            "test_size": request.test_size,
            "cv_folds": request.cv_folds if request.cross_validation else None,
        },
    )
    
    return {
        "message": f"Model training started for {request.model_type}",
        "task_id": task.id,
        "parameters": request.parameters,
        "dataset_ids": [str(d) for d in request.dataset_ids],
    }


@router.post("/automl")
async def run_automl(
    dataset_ids: List[UUID],
    target_column: str,
    task_type: str = "classification",
    time_budget: int = 3600,
    current_user: TokenPayload = Depends(get_current_user),
):
    """Run AutoML to find the best model."""
    from backend.app.tasks.ml_tasks import run_automl as run_automl_task
    
    task = run_automl_task.delay(
        dataset_ids=[str(d) for d in dataset_ids],
        target_column=target_column,
        task_type=task_type,
        time_budget=time_budget,
    )
    
    return {
        "message": f"AutoML started for {task_type}",
        "task_id": task.id,
        "time_budget": time_budget,
    }


@router.post("/predict")
async def predict(
    request: PredictRequest,
    current_user: TokenPayload = Depends(get_current_user),
):
    """Run predictions using a trained model."""
    from backend.app.tasks.ml_tasks import run_prediction
    
    task = run_prediction.delay(
        model_id=str(request.model_id),
        dataset_id=str(request.dataset_id),
        parameters=request.parameters,
    )
    
    return {
        "message": "Prediction started",
        "model_id": str(request.model_id),
        "dataset_id": str(request.dataset_id),
        "task_id": task.id,
    }


@router.post("/feature-selection")
async def feature_selection(
    request: FeatureSelectionRequest,
    target_column: Optional[str] = None,
    current_user: TokenPayload = Depends(get_current_user),
):
    """Run feature selection."""
    from backend.app.tasks.ml_tasks import run_feature_selection
    
    # Map method names
    method_map = {
        "filter": "variance",
        "wrapper": "rfe",
        "embedded": "lasso",
        "variance": "variance",
        "mutual_info": "mutual_info",
        "f_classif": "f_classif",
        "chi2": "chi2",
        "rfe": "rfe",
        "lasso": "lasso",
        "random_forest": "random_forest",
    }
    
    method = method_map.get(request.method.lower(), request.method)
    
    task = run_feature_selection.delay(
        dataset_id=str(request.dataset_id),
        method=method,
        n_features=request.n_features,
        target_column=target_column,
        parameters=request.parameters,
    )
    
    return {
        "message": f"Feature selection started using {method} method",
        "dataset_id": str(request.dataset_id),
        "task_id": task.id,
    }


@router.post("/explain")
async def explain_model(
    request: ExplainRequest,
    dataset_id: UUID = None,
    current_user: TokenPayload = Depends(get_current_user),
):
    """Generate model explanations using SHAP."""
    from backend.app.tasks.ml_tasks import generate_shap_explanations
    
    if request.method.lower() != "shap":
        return {
            "message": f"Only SHAP explanations are currently supported",
            "supported_methods": ["shap"],
        }
    
    if not dataset_id:
        raise HTTPException(
            status_code=400,
            detail="dataset_id is required for SHAP explanations",
        )
    
    task = generate_shap_explanations.delay(
        model_id=str(request.model_id),
        dataset_id=str(dataset_id),
        sample_ids=request.sample_ids,
        n_samples=request.n_samples,
    )
    
    return {
        "message": f"Generating SHAP explanations",
        "model_id": str(request.model_id),
        "task_id": task.id,
    }


@router.get("/task/{task_id}")
async def get_task_status(
    task_id: str,
    current_user: TokenPayload = Depends(get_current_user),
):
    """Get ML task status."""
    from backend.app.core.celery_app import celery_app
    
    result = celery_app.AsyncResult(task_id)
    
    response = {
        "task_id": task_id,
        "status": result.status,
        "ready": result.ready(),
    }
    
    if result.ready():
        if result.successful():
            response["result"] = result.result
        elif result.failed():
            response["error"] = str(result.result)
    elif result.status == "PROGRESS":
        response["progress"] = result.info.get("progress", 0)
        response["step"] = result.info.get("step", "")
    
    return response


@router.get("/automl/status/{task_id}")
async def get_automl_status(
    task_id: str,
    current_user: TokenPayload = Depends(get_current_user),
):
    """Get AutoML task status."""
    return await get_task_status(task_id, current_user)

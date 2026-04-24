"""
Multi-Omics ML/AI Engine
========================

Machine learning and AI components for omics analysis:
- Deep Learning Models (Neural Networks, CNNs, Transformers)
- Graph Neural Networks (GCN, GAT, GraphSAGE)
- Traditional ML (Random Forest, XGBoost, SVM)
- AutoML pipelines
- Explainability (SHAP, LIME)
- Feature Selection
"""

from backend.ml.models import get_model, list_available_models
from backend.ml.training import ModelTrainer
from backend.ml.explainability import SHAPExplainer, LIMEExplainer
from backend.ml.feature_selection import FeatureSelector
from backend.ml.automl import AutoMLPipeline

__all__ = [
    "get_model",
    "list_available_models",
    "ModelTrainer",
    "SHAPExplainer",
    "LIMEExplainer",
    "FeatureSelector",
    "AutoMLPipeline",
]

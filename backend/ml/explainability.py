"""Model Explainability."""

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class ExplanationResult:
    """Explanation result container."""

    method: str
    feature_importance: dict[str, float]
    local_explanations: list[dict] | None = None
    interaction_effects: dict | None = None

    def to_dict(self) -> dict:
        return {
            "method": self.method,
            "feature_importance": self.feature_importance,
            "local_explanations": self.local_explanations,
            "interaction_effects": self.interaction_effects,
        }


class SHAPExplainer:
    """SHAP (SHapley Additive exPlanations) explainer."""

    def __init__(self, model, model_type: str = "tree"):
        """Initialize SHAP explainer.

        Args:
            model: Fitted model
            model_type: 'tree', 'linear', 'kernel', 'deep'

        """
        self.model = model
        self.model_type = model_type
        self.explainer = None

    def fit(
        self,
        X_background: np.ndarray | pd.DataFrame,
        max_samples: int = 100,
    ) -> "SHAPExplainer":
        """Fit the SHAP explainer.

        Args:
            X_background: Background dataset for SHAP
            max_samples: Maximum samples for background

        """
        try:
            import shap

            if isinstance(X_background, pd.DataFrame):
                X_background = X_background.values

            # Subsample if necessary
            if len(X_background) > max_samples:
                idx = np.random.choice(len(X_background), max_samples, replace=False)
                X_background = X_background[idx]

            if self.model_type == "tree":
                self.explainer = shap.TreeExplainer(self.model)
            elif self.model_type == "linear":
                self.explainer = shap.LinearExplainer(self.model, X_background)
            elif self.model_type == "kernel":
                self.explainer = shap.KernelExplainer(self.model.predict, X_background)
            elif self.model_type == "deep":
                self.explainer = shap.DeepExplainer(self.model, X_background)
            else:
                raise ValueError(f"Unknown model type: {self.model_type}")

            return self

        except ImportError:
            raise ImportError("SHAP not installed. Install with: pip install shap")

    def explain(
        self,
        X: np.ndarray | pd.DataFrame,
        feature_names: list[str] | None = None,
    ) -> ExplanationResult:
        """Generate SHAP explanations.

        Args:
            X: Data to explain
            feature_names: Feature names

        Returns:
            ExplanationResult

        """
        if isinstance(X, pd.DataFrame):
            if feature_names is None:
                feature_names = X.columns.tolist()
            X = X.values

        if feature_names is None:
            feature_names = [f"feature_{i}" for i in range(X.shape[1])]

        # Calculate SHAP values
        shap_values = self.explainer.shap_values(X)

        # Handle multi-class case
        if isinstance(shap_values, list):
            shap_values = np.array(shap_values)
            if len(shap_values.shape) == 3:
                shap_values = np.abs(shap_values).mean(axis=0)

        # Global feature importance
        global_importance = np.abs(shap_values).mean(axis=0)
        feature_importance = dict(zip(feature_names, global_importance, strict=False))

        # Local explanations for each sample
        local_explanations = []
        for i in range(min(len(X), 10)):  # Limit to 10 samples
            sample_shap = shap_values[i] if len(shap_values.shape) > 1 else shap_values
            local_explanations.append(
                {
                    "sample_idx": i,
                    "shap_values": dict(zip(feature_names, sample_shap, strict=False)),
                }
            )

        return ExplanationResult(
            method="shap",
            feature_importance=feature_importance,
            local_explanations=local_explanations,
        )

    def plot_summary(self, X: np.ndarray | pd.DataFrame, feature_names: list[str] | None = None):
        """Generate SHAP summary plot."""
        import shap

        if isinstance(X, pd.DataFrame):
            if feature_names is None:
                feature_names = X.columns.tolist()
            X = X.values

        shap_values = self.explainer.shap_values(X)
        shap.summary_plot(shap_values, X, feature_names=feature_names)


class LIMEExplainer:
    """LIME (Local Interpretable Model-agnostic Explanations) explainer."""

    def __init__(self, model, task: str = "classification"):
        """Initialize LIME explainer.

        Args:
            model: Fitted model
            task: 'classification' or 'regression'

        """
        self.model = model
        self.task = task
        self.explainer = None

    def fit(
        self,
        X_train: np.ndarray | pd.DataFrame,
        feature_names: list[str] | None = None,
        class_names: list[str] | None = None,
    ) -> "LIMEExplainer":
        """Fit the LIME explainer.

        Args:
            X_train: Training data
            feature_names: Feature names
            class_names: Class names (for classification)

        """
        try:
            from lime import lime_tabular

            if isinstance(X_train, pd.DataFrame):
                if feature_names is None:
                    feature_names = X_train.columns.tolist()
                X_train = X_train.values

            if feature_names is None:
                feature_names = [f"feature_{i}" for i in range(X_train.shape[1])]

            self.feature_names = feature_names

            if self.task == "classification":
                self.explainer = lime_tabular.LimeTabularExplainer(
                    X_train,
                    feature_names=feature_names,
                    class_names=class_names,
                    mode="classification",
                )
            else:
                self.explainer = lime_tabular.LimeTabularExplainer(
                    X_train,
                    feature_names=feature_names,
                    mode="regression",
                )

            return self

        except ImportError:
            raise ImportError("LIME not installed. Install with: pip install lime")

    def explain(
        self,
        X: np.ndarray | pd.DataFrame,
        num_features: int = 10,
        num_samples: int = 5000,
    ) -> ExplanationResult:
        """Generate LIME explanations.

        Args:
            X: Data to explain
            num_features: Number of features in explanation
            num_samples: Number of samples for LIME

        Returns:
            ExplanationResult

        """
        if isinstance(X, pd.DataFrame):
            X = X.values

        # Generate explanations for samples
        local_explanations = []
        feature_weights = {f: [] for f in self.feature_names}

        for i in range(min(len(X), 10)):  # Limit to 10 samples
            if self.task == "classification":
                predict_fn = self.model.predict_proba
            else:
                predict_fn = self.model.predict

            exp = self.explainer.explain_instance(
                X[i],
                predict_fn,
                num_features=num_features,
                num_samples=num_samples,
            )

            exp_dict = dict(exp.as_list())
            local_explanations.append(
                {
                    "sample_idx": i,
                    "explanation": exp_dict,
                }
            )

            # Accumulate weights for global importance
            for feat, weight in exp.as_list():
                # Extract feature name from condition
                for fn in self.feature_names:
                    if fn in feat:
                        feature_weights[fn].append(abs(weight))
                        break

        # Calculate global feature importance
        feature_importance = {
            f: np.mean(weights) if weights else 0 for f, weights in feature_weights.items()
        }

        return ExplanationResult(
            method="lime",
            feature_importance=feature_importance,
            local_explanations=local_explanations,
        )

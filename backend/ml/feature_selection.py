"""
Feature Selection Methods
"""

from typing import Any, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass
import numpy as np
import pandas as pd
from sklearn.feature_selection import (
    SelectKBest,
    f_classif,
    f_regression,
    mutual_info_classif,
    mutual_info_regression,
    RFE,
    VarianceThreshold,
)
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor


@dataclass
class FeatureSelectionResult:
    """Feature selection result."""
    selected_features: List[str]
    feature_scores: Dict[str, float]
    n_features: int
    method: str
    
    def to_dict(self) -> Dict:
        return {
            "selected_features": self.selected_features,
            "feature_scores": self.feature_scores,
            "n_features": self.n_features,
            "method": self.method,
        }


class FeatureSelector:
    """Feature selection pipeline."""
    
    def __init__(self, task: str = "classification"):
        """
        Initialize feature selector.
        
        Args:
            task: 'classification' or 'regression'
        """
        self.task = task
    
    def variance_filter(
        self,
        X: Union[np.ndarray, pd.DataFrame],
        threshold: float = 0.0,
    ) -> FeatureSelectionResult:
        """
        Remove low-variance features.
        
        Args:
            X: Feature matrix
            threshold: Variance threshold
        
        Returns:
            FeatureSelectionResult
        """
        feature_names = X.columns.tolist() if isinstance(X, pd.DataFrame) else [f"feature_{i}" for i in range(X.shape[1])]
        X_arr = X.values if isinstance(X, pd.DataFrame) else X
        
        selector = VarianceThreshold(threshold=threshold)
        selector.fit(X_arr)
        
        selected_mask = selector.get_support()
        selected_features = [f for f, s in zip(feature_names, selected_mask) if s]
        
        variances = np.var(X_arr, axis=0)
        feature_scores = dict(zip(feature_names, variances))
        
        return FeatureSelectionResult(
            selected_features=selected_features,
            feature_scores=feature_scores,
            n_features=len(selected_features),
            method="variance_filter",
        )
    
    def univariate_selection(
        self,
        X: Union[np.ndarray, pd.DataFrame],
        y: Union[np.ndarray, pd.Series],
        method: str = "f_test",
        k: Optional[int] = None,
        percentile: float = 0.5,
    ) -> FeatureSelectionResult:
        """
        Univariate feature selection (filter method).
        
        Args:
            X: Feature matrix
            y: Target variable
            method: 'f_test' or 'mutual_info'
            k: Number of features to select (if None, use percentile)
            percentile: Percentile of features to keep (if k is None)
        
        Returns:
            FeatureSelectionResult
        """
        feature_names = X.columns.tolist() if isinstance(X, pd.DataFrame) else [f"feature_{i}" for i in range(X.shape[1])]
        X_arr = X.values if isinstance(X, pd.DataFrame) else X
        y_arr = y.values if isinstance(y, pd.Series) else y
        
        # Select scoring function
        if method == "f_test":
            score_func = f_classif if self.task == "classification" else f_regression
        elif method == "mutual_info":
            score_func = mutual_info_classif if self.task == "classification" else mutual_info_regression
        else:
            raise ValueError(f"Unknown method: {method}")
        
        # Determine k
        if k is None:
            k = max(1, int(len(feature_names) * percentile))
        
        # Select features
        selector = SelectKBest(score_func=score_func, k=k)
        selector.fit(X_arr, y_arr)
        
        selected_mask = selector.get_support()
        selected_features = [f for f, s in zip(feature_names, selected_mask) if s]
        
        feature_scores = dict(zip(feature_names, selector.scores_))
        
        return FeatureSelectionResult(
            selected_features=selected_features,
            feature_scores=feature_scores,
            n_features=len(selected_features),
            method=f"univariate_{method}",
        )
    
    def rfe_selection(
        self,
        X: Union[np.ndarray, pd.DataFrame],
        y: Union[np.ndarray, pd.Series],
        n_features: Optional[int] = None,
        step: float = 0.1,
    ) -> FeatureSelectionResult:
        """
        Recursive Feature Elimination (wrapper method).
        
        Args:
            X: Feature matrix
            y: Target variable
            n_features: Number of features to select
            step: Fraction of features to remove at each iteration
        
        Returns:
            FeatureSelectionResult
        """
        feature_names = X.columns.tolist() if isinstance(X, pd.DataFrame) else [f"feature_{i}" for i in range(X.shape[1])]
        X_arr = X.values if isinstance(X, pd.DataFrame) else X
        y_arr = y.values if isinstance(y, pd.Series) else y
        
        if n_features is None:
            n_features = max(1, len(feature_names) // 2)
        
        # Base estimator
        if self.task == "classification":
            estimator = RandomForestClassifier(n_estimators=50, random_state=42, n_jobs=-1)
        else:
            estimator = RandomForestRegressor(n_estimators=50, random_state=42, n_jobs=-1)
        
        # RFE
        selector = RFE(estimator, n_features_to_select=n_features, step=step)
        selector.fit(X_arr, y_arr)
        
        selected_mask = selector.support_
        selected_features = [f for f, s in zip(feature_names, selected_mask) if s]
        
        # Feature rankings (1 is best)
        feature_scores = dict(zip(feature_names, 1 / selector.ranking_))
        
        return FeatureSelectionResult(
            selected_features=selected_features,
            feature_scores=feature_scores,
            n_features=len(selected_features),
            method="rfe",
        )
    
    def embedded_selection(
        self,
        X: Union[np.ndarray, pd.DataFrame],
        y: Union[np.ndarray, pd.Series],
        method: str = "random_forest",
        threshold: float = 0.01,
    ) -> FeatureSelectionResult:
        """
        Embedded feature selection using model feature importances.
        
        Args:
            X: Feature matrix
            y: Target variable
            method: 'random_forest', 'lasso', 'elastic_net'
            threshold: Importance threshold for selection
        
        Returns:
            FeatureSelectionResult
        """
        feature_names = X.columns.tolist() if isinstance(X, pd.DataFrame) else [f"feature_{i}" for i in range(X.shape[1])]
        X_arr = X.values if isinstance(X, pd.DataFrame) else X
        y_arr = y.values if isinstance(y, pd.Series) else y
        
        if method == "random_forest":
            if self.task == "classification":
                model = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
            else:
                model = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
            
            model.fit(X_arr, y_arr)
            importances = model.feature_importances_
        
        elif method == "lasso":
            from sklearn.linear_model import LassoCV
            model = LassoCV(cv=5, random_state=42)
            model.fit(X_arr, y_arr)
            importances = np.abs(model.coef_)
        
        else:
            raise ValueError(f"Unknown method: {method}")
        
        # Normalize importances
        importances = importances / importances.sum() if importances.sum() > 0 else importances
        
        # Select features above threshold
        selected_mask = importances >= threshold
        selected_features = [f for f, s in zip(feature_names, selected_mask) if s]
        
        feature_scores = dict(zip(feature_names, importances))
        
        return FeatureSelectionResult(
            selected_features=selected_features,
            feature_scores=feature_scores,
            n_features=len(selected_features),
            method=f"embedded_{method}",
        )
    
    def stability_selection(
        self,
        X: Union[np.ndarray, pd.DataFrame],
        y: Union[np.ndarray, pd.Series],
        n_bootstrap: int = 100,
        threshold: float = 0.6,
    ) -> FeatureSelectionResult:
        """
        Stability selection via bootstrapping.
        
        Args:
            X: Feature matrix
            y: Target variable
            n_bootstrap: Number of bootstrap iterations
            threshold: Selection frequency threshold
        
        Returns:
            FeatureSelectionResult
        """
        feature_names = X.columns.tolist() if isinstance(X, pd.DataFrame) else [f"feature_{i}" for i in range(X.shape[1])]
        X_arr = X.values if isinstance(X, pd.DataFrame) else X
        y_arr = y.values if isinstance(y, pd.Series) else y
        
        n_samples = X_arr.shape[0]
        n_features = X_arr.shape[1]
        selection_counts = np.zeros(n_features)
        
        for _ in range(n_bootstrap):
            # Bootstrap sample
            idx = np.random.choice(n_samples, size=n_samples, replace=True)
            X_boot, y_boot = X_arr[idx], y_arr[idx]
            
            # Fit model and get importances
            if self.task == "classification":
                model = RandomForestClassifier(n_estimators=50, random_state=None, n_jobs=-1)
            else:
                model = RandomForestRegressor(n_estimators=50, random_state=None, n_jobs=-1)
            
            model.fit(X_boot, y_boot)
            
            # Select top features
            importances = model.feature_importances_
            top_k = max(1, n_features // 4)
            top_indices = np.argsort(importances)[-top_k:]
            selection_counts[top_indices] += 1
        
        # Calculate selection frequencies
        selection_freq = selection_counts / n_bootstrap
        
        # Select stable features
        selected_mask = selection_freq >= threshold
        selected_features = [f for f, s in zip(feature_names, selected_mask) if s]
        
        feature_scores = dict(zip(feature_names, selection_freq))
        
        return FeatureSelectionResult(
            selected_features=selected_features,
            feature_scores=feature_scores,
            n_features=len(selected_features),
            method="stability_selection",
        )

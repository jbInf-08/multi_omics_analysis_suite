"""
AutoML Pipeline
"""

from typing import Any, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass
import numpy as np
import pandas as pd
from sklearn.model_selection import cross_val_score

from backend.ml.models import get_model, list_available_models
from backend.ml.training import ModelTrainer, TrainingConfig


@dataclass
class AutoMLResult:
    """AutoML result container."""
    best_model_name: str
    best_model: Any
    best_score: float
    best_params: Dict[str, Any]
    all_results: List[Dict]
    
    def to_dict(self) -> Dict:
        return {
            "best_model_name": self.best_model_name,
            "best_score": self.best_score,
            "best_params": self.best_params,
            "all_results": self.all_results,
        }


class AutoMLPipeline:
    """Automated Machine Learning pipeline."""
    
    def __init__(
        self,
        task: str = "classification",
        metric: str = "accuracy",
        cv_folds: int = 5,
        max_trials: int = 50,
        time_budget: Optional[int] = None,
        random_state: int = 42,
    ):
        """
        Initialize AutoML pipeline.
        
        Args:
            task: 'classification' or 'regression'
            metric: Optimization metric
            cv_folds: Cross-validation folds
            max_trials: Maximum number of trials
            time_budget: Time budget in seconds (optional)
            random_state: Random seed
        """
        self.task = task
        self.metric = metric
        self.cv_folds = cv_folds
        self.max_trials = max_trials
        self.time_budget = time_budget
        self.random_state = random_state
        
        # Define model search space
        self._setup_search_space()
    
    def _setup_search_space(self):
        """Set up model and hyperparameter search space."""
        if self.task == "classification":
            self.model_space = {
                "random_forest": {
                    "n_estimators": [50, 100, 200],
                    "max_depth": [None, 10, 20, 30],
                    "min_samples_split": [2, 5, 10],
                },
                "xgboost": {
                    "n_estimators": [50, 100, 200],
                    "max_depth": [3, 6, 9],
                    "learning_rate": [0.01, 0.1, 0.3],
                },
                "lightgbm": {
                    "n_estimators": [50, 100, 200],
                    "max_depth": [-1, 10, 20],
                    "learning_rate": [0.01, 0.1, 0.3],
                    "num_leaves": [31, 50, 100],
                },
                "logistic_regression": {
                    "C": [0.01, 0.1, 1, 10],
                    "penalty": ["l1", "l2"],
                },
                "svm": {
                    "C": [0.1, 1, 10],
                    "kernel": ["rbf", "linear"],
                },
            }
        else:
            self.model_space = {
                "random_forest": {
                    "n_estimators": [50, 100, 200],
                    "max_depth": [None, 10, 20, 30],
                    "min_samples_split": [2, 5, 10],
                    "task": ["regression"],
                },
                "xgboost": {
                    "n_estimators": [50, 100, 200],
                    "max_depth": [3, 6, 9],
                    "learning_rate": [0.01, 0.1, 0.3],
                    "task": ["regression"],
                },
                "lightgbm": {
                    "n_estimators": [50, 100, 200],
                    "max_depth": [-1, 10, 20],
                    "learning_rate": [0.01, 0.1, 0.3],
                    "task": ["regression"],
                },
                "elastic_net": {
                    "alpha": [0.01, 0.1, 1],
                    "l1_ratio": [0.1, 0.5, 0.9],
                },
            }
    
    def run(
        self,
        X: Union[np.ndarray, pd.DataFrame],
        y: Union[np.ndarray, pd.Series],
        use_optuna: bool = True,
    ) -> AutoMLResult:
        """
        Run AutoML pipeline.
        
        Args:
            X: Feature matrix
            y: Target variable
            use_optuna: Use Optuna for hyperparameter optimization
        
        Returns:
            AutoMLResult
        """
        if use_optuna:
            return self._run_optuna(X, y)
        else:
            return self._run_grid_search(X, y)
    
    def _run_optuna(
        self,
        X: Union[np.ndarray, pd.DataFrame],
        y: Union[np.ndarray, pd.Series],
    ) -> AutoMLResult:
        """Run AutoML with Optuna."""
        try:
            import optuna
            optuna.logging.set_verbosity(optuna.logging.WARNING)
        except ImportError:
            return self._run_grid_search(X, y)
        
        X_arr = X.values if isinstance(X, pd.DataFrame) else X
        y_arr = y.values if isinstance(y, pd.Series) else y
        
        all_results = []
        
        def objective(trial):
            # Select model
            model_name = trial.suggest_categorical("model", list(self.model_space.keys()))
            params = {}
            
            # Suggest hyperparameters
            for param, values in self.model_space[model_name].items():
                if isinstance(values[0], int):
                    params[param] = trial.suggest_categorical(f"{model_name}_{param}", values)
                elif isinstance(values[0], float):
                    params[param] = trial.suggest_categorical(f"{model_name}_{param}", values)
                else:
                    params[param] = trial.suggest_categorical(f"{model_name}_{param}", values)
            
            try:
                # Create and evaluate model
                model = get_model(model_name, **params)
                
                if self.task == "classification":
                    scoring = self.metric
                else:
                    scoring = "neg_mean_squared_error" if self.metric == "mse" else f"neg_{self.metric}"
                
                scores = cross_val_score(
                    model.model,
                    X_arr,
                    y_arr,
                    cv=self.cv_folds,
                    scoring=scoring,
                )
                
                score = scores.mean()
                
                all_results.append({
                    "model": model_name,
                    "params": params,
                    "score": score,
                    "std": scores.std(),
                })
                
                return score
            except Exception as e:
                return float("-inf")
        
        # Run optimization
        study = optuna.create_study(direction="maximize")
        study.optimize(
            objective,
            n_trials=self.max_trials,
            timeout=self.time_budget,
            show_progress_bar=False,
        )
        
        # Get best model
        best_trial = study.best_trial
        best_model_name = best_trial.params["model"]
        best_params = {
            k.replace(f"{best_model_name}_", ""): v
            for k, v in best_trial.params.items()
            if k != "model"
        }
        
        # Train final model
        best_model = get_model(best_model_name, **best_params)
        best_model.fit(X_arr, y_arr)
        
        return AutoMLResult(
            best_model_name=best_model_name,
            best_model=best_model,
            best_score=best_trial.value,
            best_params=best_params,
            all_results=sorted(all_results, key=lambda x: x["score"], reverse=True),
        )
    
    def _run_grid_search(
        self,
        X: Union[np.ndarray, pd.DataFrame],
        y: Union[np.ndarray, pd.Series],
    ) -> AutoMLResult:
        """Run AutoML with simple grid search."""
        from itertools import product
        
        X_arr = X.values if isinstance(X, pd.DataFrame) else X
        y_arr = y.values if isinstance(y, pd.Series) else y
        
        all_results = []
        best_score = float("-inf")
        best_model = None
        best_model_name = None
        best_params = None
        
        for model_name, param_space in self.model_space.items():
            # Generate parameter combinations
            param_names = list(param_space.keys())
            param_values = list(param_space.values())
            
            for values in product(*param_values):
                params = dict(zip(param_names, values))
                
                try:
                    model = get_model(model_name, **params)
                    
                    if self.task == "classification":
                        scoring = self.metric
                    else:
                        scoring = "neg_mean_squared_error"
                    
                    scores = cross_val_score(
                        model.model,
                        X_arr,
                        y_arr,
                        cv=self.cv_folds,
                        scoring=scoring,
                    )
                    
                    score = scores.mean()
                    
                    all_results.append({
                        "model": model_name,
                        "params": params,
                        "score": score,
                        "std": scores.std(),
                    })
                    
                    if score > best_score:
                        best_score = score
                        best_model_name = model_name
                        best_params = params
                
                except Exception as e:
                    continue
        
        # Train final model
        if best_model_name:
            best_model = get_model(best_model_name, **best_params)
            best_model.fit(X_arr, y_arr)
        
        return AutoMLResult(
            best_model_name=best_model_name or "none",
            best_model=best_model,
            best_score=best_score,
            best_params=best_params or {},
            all_results=sorted(all_results, key=lambda x: x["score"], reverse=True),
        )

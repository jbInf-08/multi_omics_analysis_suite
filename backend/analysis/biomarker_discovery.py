"""
Biomarker Discovery Pipeline
============================

Comprehensive biomarker identification with:
- Consensus scoring across multiple feature selection methods
- Stability selection with bootstrap resampling
- Multi-method validation
- Biomarker ranking and prioritization
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field
from enum import Enum
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LassoCV, ElasticNetCV, LogisticRegressionCV
from sklearn.feature_selection import (
    SelectKBest,
    f_classif,
    mutual_info_classif,
    RFE,
    SelectFromModel,
)
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import StratifiedKFold
from sklearn.svm import LinearSVC
import xgboost as xgb
import lightgbm as lgb
from scipy import stats

logger = logging.getLogger(__name__)


class FeatureSelectionMethod(str, Enum):
    """Available feature selection methods."""
    RANDOM_FOREST = "random_forest"
    XGBOOST = "xgboost"
    LIGHTGBM = "lightgbm"
    LASSO = "lasso"
    ELASTIC_NET = "elastic_net"
    MUTUAL_INFO = "mutual_info"
    F_CLASSIF = "f_classif"
    RFE = "rfe"
    SVM_L1 = "svm_l1"
    LOGISTIC_L1 = "logistic_l1"
    BORUTA = "boruta"
    MRMR = "mrmr"


@dataclass
class BiomarkerCandidate:
    """Represents a potential biomarker candidate."""
    feature_name: str
    consensus_score: float
    stability_score: float
    selection_frequency: float
    method_scores: Dict[str, float]
    rank: int
    p_value: Optional[float] = None
    effect_size: Optional[float] = None
    fold_change: Optional[float] = None
    auc: Optional[float] = None
    clinical_relevance: Optional[str] = None
    validation_status: str = "pending"


@dataclass
class BiomarkerDiscoveryResult:
    """Results from biomarker discovery pipeline."""
    candidates: List[BiomarkerCandidate]
    consensus_matrix: pd.DataFrame
    stability_scores: Dict[str, float]
    method_results: Dict[str, List[str]]
    n_samples: int
    n_features: int
    n_selected: int
    parameters: Dict[str, Any]
    execution_time: float


class StabilitySelector:
    """
    Stability Selection for robust feature selection.
    
    Implements the stability selection framework from Meinshausen & Bühlmann (2010)
    with bootstrap resampling to identify stable features.
    """
    
    def __init__(
        self,
        base_selector: str = "lasso",
        n_bootstrap: int = 100,
        sample_fraction: float = 0.5,
        threshold: float = 0.6,
        lambda_grid: Optional[np.ndarray] = None,
        n_jobs: int = -1,
        random_state: int = 42,
    ):
        """
        Initialize stability selector.
        
        Args:
            base_selector: Base feature selection method
            n_bootstrap: Number of bootstrap iterations
            sample_fraction: Fraction of samples per bootstrap
            threshold: Selection probability threshold
            lambda_grid: Regularization parameter grid
            n_jobs: Number of parallel jobs
            random_state: Random seed
        """
        self.base_selector = base_selector
        self.n_bootstrap = n_bootstrap
        self.sample_fraction = sample_fraction
        self.threshold = threshold
        self.lambda_grid = lambda_grid
        self.n_jobs = n_jobs
        self.random_state = random_state
        
        self.selection_probabilities_: Optional[np.ndarray] = None
        self.selected_features_: Optional[np.ndarray] = None
        self.stability_scores_: Optional[Dict[str, float]] = None
    
    def fit(self, X: np.ndarray, y: np.ndarray) -> "StabilitySelector":
        """
        Fit stability selector using bootstrap resampling.
        
        Args:
            X: Feature matrix (n_samples, n_features)
            y: Target vector
            
        Returns:
            Fitted StabilitySelector
        """
        n_samples, n_features = X.shape
        selection_counts = np.zeros(n_features)
        
        rng = np.random.RandomState(self.random_state)
        subsample_size = int(n_samples * self.sample_fraction)
        
        logger.info(f"Running stability selection with {self.n_bootstrap} bootstrap iterations")
        
        for i in range(self.n_bootstrap):
            # Bootstrap sample
            indices = rng.choice(n_samples, size=subsample_size, replace=False)
            X_sub, y_sub = X[indices], y[indices]
            
            # Apply base selector
            selected = self._apply_base_selector(X_sub, y_sub, n_features)
            selection_counts += selected
            
            if (i + 1) % 20 == 0:
                logger.debug(f"Completed {i + 1}/{self.n_bootstrap} bootstrap iterations")
        
        # Calculate selection probabilities
        self.selection_probabilities_ = selection_counts / self.n_bootstrap
        self.selected_features_ = np.where(self.selection_probabilities_ >= self.threshold)[0]
        
        # Calculate stability scores
        self.stability_scores_ = {
            f"feature_{i}": prob 
            for i, prob in enumerate(self.selection_probabilities_)
        }
        
        logger.info(f"Selected {len(self.selected_features_)} stable features")
        return self
    
    def _apply_base_selector(
        self, X: np.ndarray, y: np.ndarray, n_features: int
    ) -> np.ndarray:
        """Apply base feature selection method."""
        selected = np.zeros(n_features)
        
        try:
            if self.base_selector == "lasso":
                model = LassoCV(cv=3, random_state=self.random_state, max_iter=5000)
                model.fit(X, y)
                selected[np.abs(model.coef_) > 1e-6] = 1
                
            elif self.base_selector == "elastic_net":
                model = ElasticNetCV(cv=3, random_state=self.random_state, max_iter=5000)
                model.fit(X, y)
                selected[np.abs(model.coef_) > 1e-6] = 1
                
            elif self.base_selector == "random_forest":
                model = RandomForestClassifier(
                    n_estimators=100, random_state=self.random_state, n_jobs=1
                )
                model.fit(X, y)
                importance = model.feature_importances_
                threshold = np.percentile(importance, 75)
                selected[importance >= threshold] = 1
                
            elif self.base_selector == "logistic_l1":
                model = LogisticRegressionCV(
                    cv=3, penalty="l1", solver="saga",
                    random_state=self.random_state, max_iter=5000
                )
                model.fit(X, y)
                selected[np.abs(model.coef_[0]) > 1e-6] = 1
                
            elif self.base_selector == "svm_l1":
                model = LinearSVC(penalty="l1", dual=False, random_state=self.random_state)
                model.fit(X, y)
                selected[np.abs(model.coef_[0]) > 1e-6] = 1
                
        except Exception as e:
            logger.warning(f"Base selector failed: {e}")
        
        return selected
    
    def transform(self, X: np.ndarray) -> np.ndarray:
        """Transform data to selected features."""
        if self.selected_features_ is None:
            raise ValueError("StabilitySelector not fitted")
        return X[:, self.selected_features_]
    
    def fit_transform(self, X: np.ndarray, y: np.ndarray) -> np.ndarray:
        """Fit and transform in one step."""
        return self.fit(X, y).transform(X)
    
    def get_support(self) -> np.ndarray:
        """Get boolean mask of selected features."""
        if self.selection_probabilities_ is None:
            raise ValueError("StabilitySelector not fitted")
        return self.selection_probabilities_ >= self.threshold


class ConsensusScorer:
    """
    Consensus scoring across multiple feature selection methods.
    
    Combines results from multiple methods to create robust
    biomarker rankings with confidence estimates.
    """
    
    def __init__(
        self,
        methods: Optional[List[FeatureSelectionMethod]] = None,
        n_top_features: int = 100,
        weights: Optional[Dict[str, float]] = None,
        aggregation: str = "weighted_mean",
        normalize_scores: bool = True,
        n_jobs: int = -1,
    ):
        """
        Initialize consensus scorer.
        
        Args:
            methods: List of feature selection methods
            n_top_features: Number of top features to consider per method
            weights: Method weights for aggregation
            aggregation: Aggregation strategy ('weighted_mean', 'rank_product', 'borda')
            normalize_scores: Whether to normalize scores
            n_jobs: Number of parallel jobs
        """
        self.methods = methods or [
            FeatureSelectionMethod.RANDOM_FOREST,
            FeatureSelectionMethod.XGBOOST,
            FeatureSelectionMethod.LASSO,
            FeatureSelectionMethod.MUTUAL_INFO,
            FeatureSelectionMethod.F_CLASSIF,
        ]
        self.n_top_features = n_top_features
        self.weights = weights or {m.value: 1.0 for m in self.methods}
        self.aggregation = aggregation
        self.normalize_scores = normalize_scores
        self.n_jobs = n_jobs
        
        self.method_scores_: Optional[Dict[str, np.ndarray]] = None
        self.consensus_scores_: Optional[np.ndarray] = None
        self.feature_rankings_: Optional[np.ndarray] = None
    
    def fit(
        self, X: np.ndarray, y: np.ndarray, 
        feature_names: Optional[List[str]] = None
    ) -> "ConsensusScorer":
        """
        Compute consensus scores from multiple methods.
        
        Args:
            X: Feature matrix
            y: Target vector
            feature_names: Optional feature names
            
        Returns:
            Fitted ConsensusScorer
        """
        n_features = X.shape[1]
        self.feature_names_ = feature_names or [f"feature_{i}" for i in range(n_features)]
        self.method_scores_ = {}
        
        logger.info(f"Computing consensus scores from {len(self.methods)} methods")
        
        # Run each method
        with ThreadPoolExecutor(max_workers=self.n_jobs if self.n_jobs > 0 else None) as executor:
            futures = {
                executor.submit(self._compute_method_scores, method, X, y): method
                for method in self.methods
            }
            
            for future in as_completed(futures):
                method = futures[future]
                try:
                    scores = future.result()
                    self.method_scores_[method.value] = scores
                    logger.debug(f"Completed {method.value}")
                except Exception as e:
                    logger.warning(f"Method {method.value} failed: {e}")
                    self.method_scores_[method.value] = np.zeros(n_features)
        
        # Compute consensus
        self._compute_consensus()
        
        return self
    
    def _compute_method_scores(
        self, method: FeatureSelectionMethod, X: np.ndarray, y: np.ndarray
    ) -> np.ndarray:
        """Compute importance scores for a single method."""
        n_features = X.shape[1]
        scores = np.zeros(n_features)
        
        try:
            if method == FeatureSelectionMethod.RANDOM_FOREST:
                model = RandomForestClassifier(n_estimators=200, random_state=42, n_jobs=1)
                model.fit(X, y)
                scores = model.feature_importances_
                
            elif method == FeatureSelectionMethod.XGBOOST:
                model = xgb.XGBClassifier(
                    n_estimators=200, random_state=42, 
                    use_label_encoder=False, eval_metric="logloss"
                )
                model.fit(X, y)
                scores = model.feature_importances_
                
            elif method == FeatureSelectionMethod.LIGHTGBM:
                model = lgb.LGBMClassifier(n_estimators=200, random_state=42, verbose=-1)
                model.fit(X, y)
                scores = model.feature_importances_ / model.feature_importances_.sum()
                
            elif method == FeatureSelectionMethod.LASSO:
                model = LassoCV(cv=5, random_state=42, max_iter=5000)
                # Convert to continuous if classification
                y_cont = y.astype(float)
                model.fit(X, y_cont)
                scores = np.abs(model.coef_)
                
            elif method == FeatureSelectionMethod.ELASTIC_NET:
                model = ElasticNetCV(cv=5, random_state=42, max_iter=5000)
                y_cont = y.astype(float)
                model.fit(X, y_cont)
                scores = np.abs(model.coef_)
                
            elif method == FeatureSelectionMethod.MUTUAL_INFO:
                scores = mutual_info_classif(X, y, random_state=42)
                
            elif method == FeatureSelectionMethod.F_CLASSIF:
                scores, _ = f_classif(X, y)
                scores = np.nan_to_num(scores, nan=0.0)
                
            elif method == FeatureSelectionMethod.RFE:
                base_model = RandomForestClassifier(n_estimators=50, random_state=42)
                selector = RFE(base_model, n_features_to_select=min(50, n_features // 2))
                selector.fit(X, y)
                # Convert ranking to scores (lower rank = higher score)
                scores = 1.0 / selector.ranking_
                
            elif method == FeatureSelectionMethod.LOGISTIC_L1:
                model = LogisticRegressionCV(
                    cv=5, penalty="l1", solver="saga", random_state=42, max_iter=5000
                )
                model.fit(X, y)
                scores = np.abs(model.coef_[0])
                
        except Exception as e:
            logger.warning(f"Method {method.value} computation failed: {e}")
        
        return scores
    
    def _compute_consensus(self) -> None:
        """Compute consensus scores from method results."""
        n_features = len(self.feature_names_)
        
        # Stack and normalize scores
        score_matrix = np.zeros((len(self.method_scores_), n_features))
        weights = []
        
        for i, (method_name, scores) in enumerate(self.method_scores_.items()):
            if self.normalize_scores:
                if scores.max() > 0:
                    scores = scores / scores.max()
            score_matrix[i] = scores
            weights.append(self.weights.get(method_name, 1.0))
        
        weights = np.array(weights)
        weights = weights / weights.sum()
        
        if self.aggregation == "weighted_mean":
            self.consensus_scores_ = np.average(score_matrix, axis=0, weights=weights)
            
        elif self.aggregation == "rank_product":
            # Convert scores to ranks
            rank_matrix = np.zeros_like(score_matrix)
            for i in range(score_matrix.shape[0]):
                rank_matrix[i] = stats.rankdata(-score_matrix[i])
            # Geometric mean of ranks (lower is better)
            rank_product = np.exp(np.mean(np.log(rank_matrix + 1), axis=0))
            self.consensus_scores_ = 1.0 / rank_product
            
        elif self.aggregation == "borda":
            # Borda count aggregation
            borda_scores = np.zeros(n_features)
            for i in range(score_matrix.shape[0]):
                ranks = stats.rankdata(score_matrix[i])
                borda_scores += ranks * weights[i]
            self.consensus_scores_ = borda_scores
        
        # Compute rankings
        self.feature_rankings_ = stats.rankdata(-self.consensus_scores_).astype(int)
    
    def get_top_features(self, n: int = 50) -> pd.DataFrame:
        """Get top N features by consensus score."""
        if self.consensus_scores_ is None:
            raise ValueError("ConsensusScorer not fitted")
        
        indices = np.argsort(-self.consensus_scores_)[:n]
        
        results = []
        for rank, idx in enumerate(indices, 1):
            result = {
                "rank": rank,
                "feature": self.feature_names_[idx],
                "consensus_score": self.consensus_scores_[idx],
            }
            for method_name, scores in self.method_scores_.items():
                result[f"{method_name}_score"] = scores[idx]
            results.append(result)
        
        return pd.DataFrame(results)


class BiomarkerDiscoveryPipeline:
    """
    Comprehensive biomarker discovery pipeline.
    
    Integrates multiple feature selection approaches with
    stability selection and consensus scoring for robust
    biomarker identification.
    """
    
    def __init__(
        self,
        # Consensus scoring parameters
        methods: Optional[List[FeatureSelectionMethod]] = None,
        method_weights: Optional[Dict[str, float]] = None,
        aggregation: str = "weighted_mean",
        
        # Stability selection parameters
        use_stability_selection: bool = True,
        n_bootstrap: int = 100,
        stability_threshold: float = 0.6,
        
        # Cross-validation parameters
        n_cv_folds: int = 5,
        
        # Output parameters
        n_top_biomarkers: int = 50,
        min_consensus_score: float = 0.1,
        
        # Execution parameters
        n_jobs: int = -1,
        random_state: int = 42,
        verbose: bool = True,
    ):
        """
        Initialize biomarker discovery pipeline.
        
        Args:
            methods: Feature selection methods to use
            method_weights: Weights for consensus aggregation
            aggregation: Consensus aggregation strategy
            use_stability_selection: Whether to use stability selection
            n_bootstrap: Number of bootstrap iterations
            stability_threshold: Stability selection threshold
            n_cv_folds: Number of cross-validation folds
            n_top_biomarkers: Number of top biomarkers to return
            min_consensus_score: Minimum consensus score threshold
            n_jobs: Number of parallel jobs
            random_state: Random seed
            verbose: Verbosity flag
        """
        self.methods = methods or [
            FeatureSelectionMethod.RANDOM_FOREST,
            FeatureSelectionMethod.XGBOOST,
            FeatureSelectionMethod.LIGHTGBM,
            FeatureSelectionMethod.LASSO,
            FeatureSelectionMethod.ELASTIC_NET,
            FeatureSelectionMethod.MUTUAL_INFO,
            FeatureSelectionMethod.F_CLASSIF,
        ]
        self.method_weights = method_weights
        self.aggregation = aggregation
        self.use_stability_selection = use_stability_selection
        self.n_bootstrap = n_bootstrap
        self.stability_threshold = stability_threshold
        self.n_cv_folds = n_cv_folds
        self.n_top_biomarkers = n_top_biomarkers
        self.min_consensus_score = min_consensus_score
        self.n_jobs = n_jobs
        self.random_state = random_state
        self.verbose = verbose
        
        # Components
        self.consensus_scorer_ = None
        self.stability_selector_ = None
        self.scaler_ = StandardScaler()
        
        # Results
        self.results_: Optional[BiomarkerDiscoveryResult] = None
    
    def fit(
        self,
        X: Union[np.ndarray, pd.DataFrame],
        y: Union[np.ndarray, pd.Series],
        feature_names: Optional[List[str]] = None,
        sample_groups: Optional[np.ndarray] = None,
    ) -> "BiomarkerDiscoveryPipeline":
        """
        Run biomarker discovery pipeline.
        
        Args:
            X: Feature matrix (samples x features)
            y: Target labels
            feature_names: Names of features
            sample_groups: Optional sample groupings for stratification
            
        Returns:
            Fitted BiomarkerDiscoveryPipeline
        """
        import time
        start_time = time.time()
        
        # Convert to numpy
        if isinstance(X, pd.DataFrame):
            feature_names = feature_names or X.columns.tolist()
            X = X.values
        if isinstance(y, pd.Series):
            y = y.values
        
        n_samples, n_features = X.shape
        feature_names = feature_names or [f"feature_{i}" for i in range(n_features)]
        
        if self.verbose:
            logger.info(f"Starting biomarker discovery: {n_samples} samples, {n_features} features")
        
        # Preprocessing
        X_scaled = self.scaler_.fit_transform(X)
        
        # 1. Consensus Scoring
        self.consensus_scorer_ = ConsensusScorer(
            methods=self.methods,
            n_top_features=self.n_top_biomarkers * 2,
            weights=self.method_weights,
            aggregation=self.aggregation,
            n_jobs=self.n_jobs,
        )
        self.consensus_scorer_.fit(X_scaled, y, feature_names)
        
        # 2. Stability Selection (optional)
        stability_scores = {}
        if self.use_stability_selection:
            self.stability_selector_ = StabilitySelector(
                base_selector="lasso",
                n_bootstrap=self.n_bootstrap,
                threshold=self.stability_threshold,
                random_state=self.random_state,
            )
            self.stability_selector_.fit(X_scaled, y)
            stability_scores = {
                feature_names[i]: prob
                for i, prob in enumerate(self.stability_selector_.selection_probabilities_)
            }
        
        # 3. Create biomarker candidates
        candidates = self._create_candidates(
            X, y, feature_names, 
            self.consensus_scorer_.consensus_scores_,
            stability_scores
        )
        
        # 4. Compute additional statistics
        candidates = self._compute_additional_stats(X, y, candidates)
        
        # 5. Rank and filter candidates
        candidates = sorted(candidates, key=lambda c: c.consensus_score, reverse=True)
        candidates = [c for c in candidates if c.consensus_score >= self.min_consensus_score]
        candidates = candidates[:self.n_top_biomarkers]
        
        # Update ranks
        for i, candidate in enumerate(candidates, 1):
            candidate.rank = i
        
        # Build results
        execution_time = time.time() - start_time
        
        self.results_ = BiomarkerDiscoveryResult(
            candidates=candidates,
            consensus_matrix=self.consensus_scorer_.get_top_features(self.n_top_biomarkers),
            stability_scores=stability_scores,
            method_results={
                method: self._get_top_features_for_method(method, feature_names)
                for method in self.methods
            },
            n_samples=n_samples,
            n_features=n_features,
            n_selected=len(candidates),
            parameters={
                "methods": [m.value for m in self.methods],
                "n_bootstrap": self.n_bootstrap,
                "stability_threshold": self.stability_threshold,
                "aggregation": self.aggregation,
            },
            execution_time=execution_time,
        )
        
        if self.verbose:
            logger.info(
                f"Biomarker discovery complete: {len(candidates)} biomarkers identified "
                f"in {execution_time:.2f}s"
            )
        
        return self
    
    def _create_candidates(
        self,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: List[str],
        consensus_scores: np.ndarray,
        stability_scores: Dict[str, float],
    ) -> List[BiomarkerCandidate]:
        """Create biomarker candidates from scores."""
        candidates = []
        
        for i, name in enumerate(feature_names):
            # Compute selection frequency across methods
            selection_count = sum(
                1 for scores in self.consensus_scorer_.method_scores_.values()
                if scores[i] > np.percentile(scores, 75)
            )
            selection_freq = selection_count / len(self.consensus_scorer_.method_scores_)
            
            candidate = BiomarkerCandidate(
                feature_name=name,
                consensus_score=consensus_scores[i],
                stability_score=stability_scores.get(name, 0.0),
                selection_frequency=selection_freq,
                method_scores={
                    method: float(scores[i])
                    for method, scores in self.consensus_scorer_.method_scores_.items()
                },
                rank=0,  # Will be set later
            )
            candidates.append(candidate)
        
        return candidates
    
    def _compute_additional_stats(
        self,
        X: np.ndarray,
        y: np.ndarray,
        candidates: List[BiomarkerCandidate],
    ) -> List[BiomarkerCandidate]:
        """Compute additional statistics for candidates."""
        feature_names = [c.feature_name for c in candidates]
        feature_idx = {name: i for i, name in enumerate(
            self.consensus_scorer_.feature_names_
        )}
        
        unique_classes = np.unique(y)
        if len(unique_classes) == 2:
            # Binary classification - compute fold change and p-value
            for candidate in candidates:
                idx = feature_idx.get(candidate.feature_name)
                if idx is None:
                    continue
                
                group1 = X[y == unique_classes[0], idx]
                group2 = X[y == unique_classes[1], idx]
                
                # T-test
                try:
                    _, p_value = stats.ttest_ind(group1, group2)
                    candidate.p_value = float(p_value)
                except:
                    candidate.p_value = 1.0
                
                # Effect size (Cohen's d)
                try:
                    pooled_std = np.sqrt(
                        ((len(group1) - 1) * group1.std() ** 2 + 
                         (len(group2) - 1) * group2.std() ** 2) /
                        (len(group1) + len(group2) - 2)
                    )
                    if pooled_std > 0:
                        candidate.effect_size = float(
                            (group2.mean() - group1.mean()) / pooled_std
                        )
                except:
                    pass
                
                # Fold change (log2)
                try:
                    mean1, mean2 = group1.mean(), group2.mean()
                    if mean1 > 0 and mean2 > 0:
                        candidate.fold_change = float(np.log2(mean2 / mean1))
                except:
                    pass
        
        return candidates
    
    def _get_top_features_for_method(
        self, method: FeatureSelectionMethod, feature_names: List[str]
    ) -> List[str]:
        """Get top features for a specific method."""
        scores = self.consensus_scorer_.method_scores_.get(method.value)
        if scores is None:
            return []
        
        indices = np.argsort(-scores)[:self.n_top_biomarkers]
        return [feature_names[i] for i in indices]
    
    def get_candidates(self) -> List[BiomarkerCandidate]:
        """Get identified biomarker candidates."""
        if self.results_ is None:
            raise ValueError("Pipeline not fitted")
        return self.results_.candidates
    
    def get_results_dataframe(self) -> pd.DataFrame:
        """Get results as a DataFrame."""
        if self.results_ is None:
            raise ValueError("Pipeline not fitted")
        
        data = []
        for c in self.results_.candidates:
            row = {
                "rank": c.rank,
                "feature": c.feature_name,
                "consensus_score": c.consensus_score,
                "stability_score": c.stability_score,
                "selection_frequency": c.selection_frequency,
                "p_value": c.p_value,
                "effect_size": c.effect_size,
                "fold_change": c.fold_change,
            }
            row.update({f"method_{k}": v for k, v in c.method_scores.items()})
            data.append(row)
        
        return pd.DataFrame(data)
    
    def transform(self, X: Union[np.ndarray, pd.DataFrame]) -> np.ndarray:
        """Transform data to selected biomarker features."""
        if self.results_ is None:
            raise ValueError("Pipeline not fitted")
        
        if isinstance(X, pd.DataFrame):
            selected_features = [c.feature_name for c in self.results_.candidates]
            return X[selected_features].values
        else:
            feature_names = self.consensus_scorer_.feature_names_
            selected_indices = [
                feature_names.index(c.feature_name) 
                for c in self.results_.candidates
            ]
            return X[:, selected_indices]
    
    def fit_transform(
        self,
        X: Union[np.ndarray, pd.DataFrame],
        y: Union[np.ndarray, pd.Series],
        feature_names: Optional[List[str]] = None,
    ) -> np.ndarray:
        """Fit and transform in one step."""
        self.fit(X, y, feature_names)
        return self.transform(X)

"""
Statistical Analysis Pipeline
=============================

Comprehensive statistical analysis including:
- Parametric tests (t-test, ANOVA)
- Non-parametric tests (Wilcoxon, Kruskal-Wallis)
- Effect size calculations (Cohen's d, Cliff's delta, eta-squared)
- Multiple testing correction (FDR, Bonferroni, Holm)
- Differential expression analysis
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field
from enum import Enum
import logging
from scipy import stats
from scipy.stats import (
    ttest_ind,
    ttest_rel,
    mannwhitneyu,
    wilcoxon,
    f_oneway,
    kruskal,
    pearsonr,
    spearmanr,
    chi2_contingency,
    fisher_exact,
    shapiro,
    levene,
    bartlett,
)
from statsmodels.stats.multitest import multipletests
from statsmodels.stats.power import TTestIndPower, TTestPower
import statsmodels.api as sm
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)


class StatisticalTest(str, Enum):
    """Available statistical tests."""
    TTEST_IND = "ttest_independent"
    TTEST_PAIRED = "ttest_paired"
    WELCH_TTEST = "welch_ttest"
    MANN_WHITNEY = "mann_whitney"
    WILCOXON = "wilcoxon"
    ANOVA = "anova"
    KRUSKAL_WALLIS = "kruskal_wallis"
    CHI_SQUARE = "chi_square"
    FISHER_EXACT = "fisher_exact"
    PEARSON = "pearson"
    SPEARMAN = "spearman"


class MultipleTestingMethod(str, Enum):
    """Multiple testing correction methods."""
    BONFERRONI = "bonferroni"
    HOLM = "holm"
    SIDAK = "sidak"
    HOLM_SIDAK = "holm-sidak"
    FDR_BH = "fdr_bh"
    FDR_BY = "fdr_by"
    FDR_TSBH = "fdr_tsbh"
    FDR_TSBKY = "fdr_tsbky"


@dataclass
class TestResult:
    """Result from a single statistical test."""
    feature: str
    test_name: str
    statistic: float
    p_value: float
    adjusted_p_value: Optional[float] = None
    effect_size: Optional[float] = None
    effect_size_type: Optional[str] = None
    confidence_interval: Optional[Tuple[float, float]] = None
    mean_group1: Optional[float] = None
    mean_group2: Optional[float] = None
    std_group1: Optional[float] = None
    std_group2: Optional[float] = None
    n_group1: Optional[int] = None
    n_group2: Optional[int] = None
    fold_change: Optional[float] = None
    log2_fold_change: Optional[float] = None
    is_significant: bool = False
    direction: Optional[str] = None  # "up", "down", or None


@dataclass
class StatisticalAnalysisResult:
    """Results from statistical analysis pipeline."""
    results: List[TestResult]
    summary: pd.DataFrame
    significant_features: List[str]
    n_tests: int
    n_significant: int
    correction_method: str
    alpha: float
    parameters: Dict[str, Any]


class EffectSizeCalculator:
    """
    Calculate various effect size measures.
    
    Supports:
    - Cohen's d (standardized mean difference)
    - Hedges' g (bias-corrected Cohen's d)
    - Glass's delta
    - Cliff's delta (non-parametric)
    - Eta-squared (ANOVA)
    - Omega-squared (ANOVA)
    - Odds ratio
    - Risk ratio
    """
    
    @staticmethod
    def cohens_d(
        group1: np.ndarray, 
        group2: np.ndarray,
        pooled: bool = True
    ) -> Tuple[float, Tuple[float, float]]:
        """
        Calculate Cohen's d effect size.
        
        Args:
            group1: First group data
            group2: Second group data
            pooled: Use pooled standard deviation
            
        Returns:
            Effect size and 95% CI
        """
        n1, n2 = len(group1), len(group2)
        mean1, mean2 = group1.mean(), group2.mean()
        var1, var2 = group1.var(ddof=1), group2.var(ddof=1)
        
        if pooled:
            # Pooled standard deviation
            pooled_std = np.sqrt(
                ((n1 - 1) * var1 + (n2 - 1) * var2) / (n1 + n2 - 2)
            )
        else:
            # Use control group (group1) std
            pooled_std = np.sqrt(var1)
        
        if pooled_std == 0:
            return 0.0, (0.0, 0.0)
        
        d = (mean2 - mean1) / pooled_std
        
        # Confidence interval using non-central t
        se = np.sqrt((n1 + n2) / (n1 * n2) + d**2 / (2 * (n1 + n2)))
        ci = (d - 1.96 * se, d + 1.96 * se)
        
        return d, ci
    
    @staticmethod
    def hedges_g(group1: np.ndarray, group2: np.ndarray) -> Tuple[float, Tuple[float, float]]:
        """
        Calculate Hedges' g (bias-corrected Cohen's d).
        
        Args:
            group1: First group data
            group2: Second group data
            
        Returns:
            Effect size and 95% CI
        """
        d, ci = EffectSizeCalculator.cohens_d(group1, group2)
        
        # Bias correction factor
        n = len(group1) + len(group2)
        correction = 1 - (3 / (4 * n - 9))
        
        g = d * correction
        ci_corrected = (ci[0] * correction, ci[1] * correction)
        
        return g, ci_corrected
    
    @staticmethod
    def cliffs_delta(group1: np.ndarray, group2: np.ndarray) -> Tuple[float, str]:
        """
        Calculate Cliff's delta (non-parametric effect size).
        
        Args:
            group1: First group data
            group2: Second group data
            
        Returns:
            Effect size and interpretation
        """
        n1, n2 = len(group1), len(group2)
        
        # Count dominance
        more = 0
        less = 0
        for x in group1:
            for y in group2:
                if x > y:
                    more += 1
                elif x < y:
                    less += 1
        
        delta = (more - less) / (n1 * n2)
        
        # Interpretation
        abs_delta = abs(delta)
        if abs_delta < 0.147:
            interpretation = "negligible"
        elif abs_delta < 0.33:
            interpretation = "small"
        elif abs_delta < 0.474:
            interpretation = "medium"
        else:
            interpretation = "large"
        
        return delta, interpretation
    
    @staticmethod
    def eta_squared(
        groups: List[np.ndarray], 
        ss_between: Optional[float] = None,
        ss_total: Optional[float] = None
    ) -> float:
        """
        Calculate eta-squared for ANOVA.
        
        Args:
            groups: List of group data arrays
            ss_between: Sum of squares between (optional)
            ss_total: Total sum of squares (optional)
            
        Returns:
            Eta-squared effect size
        """
        if ss_between is not None and ss_total is not None:
            return ss_between / ss_total if ss_total > 0 else 0.0
        
        # Compute from data
        all_data = np.concatenate(groups)
        grand_mean = all_data.mean()
        
        ss_total = np.sum((all_data - grand_mean) ** 2)
        ss_between = sum(
            len(g) * (g.mean() - grand_mean) ** 2 for g in groups
        )
        
        return ss_between / ss_total if ss_total > 0 else 0.0
    
    @staticmethod
    def omega_squared(
        groups: List[np.ndarray],
        f_statistic: Optional[float] = None,
        df_between: Optional[int] = None,
        df_within: Optional[int] = None,
    ) -> float:
        """
        Calculate omega-squared (less biased than eta-squared).
        
        Args:
            groups: List of group data arrays
            f_statistic: F-statistic from ANOVA
            df_between: Degrees of freedom between groups
            df_within: Degrees of freedom within groups
            
        Returns:
            Omega-squared effect size
        """
        if f_statistic is not None and df_between is not None and df_within is not None:
            # From F-statistic
            numerator = (df_between * (f_statistic - 1))
            denominator = (df_between * (f_statistic - 1)) + df_within + df_between + 1
            return numerator / denominator if denominator > 0 else 0.0
        
        # Compute from data
        all_data = np.concatenate(groups)
        n_total = len(all_data)
        k = len(groups)
        grand_mean = all_data.mean()
        
        ss_total = np.sum((all_data - grand_mean) ** 2)
        ss_between = sum(
            len(g) * (g.mean() - grand_mean) ** 2 for g in groups
        )
        ss_within = ss_total - ss_between
        
        ms_within = ss_within / (n_total - k)
        
        numerator = ss_between - (k - 1) * ms_within
        denominator = ss_total + ms_within
        
        return numerator / denominator if denominator > 0 else 0.0
    
    @staticmethod
    def interpret_cohens_d(d: float) -> str:
        """Interpret Cohen's d effect size."""
        abs_d = abs(d)
        if abs_d < 0.2:
            return "negligible"
        elif abs_d < 0.5:
            return "small"
        elif abs_d < 0.8:
            return "medium"
        else:
            return "large"


class MultipleTestingCorrection:
    """
    Multiple testing correction methods.
    
    Implements various FDR and FWER controlling procedures.
    """
    
    @staticmethod
    def correct(
        p_values: np.ndarray,
        method: Union[str, MultipleTestingMethod] = MultipleTestingMethod.FDR_BH,
        alpha: float = 0.05,
    ) -> Tuple[np.ndarray, np.ndarray, float, float]:
        """
        Apply multiple testing correction.
        
        Args:
            p_values: Array of p-values
            method: Correction method
            alpha: Significance level
            
        Returns:
            Tuple of (reject, adjusted_p, alpha_sidak, alpha_bonf)
        """
        if isinstance(method, MultipleTestingMethod):
            method = method.value
        
        reject, pvals_corrected, alpha_sidak, alpha_bonf = multipletests(
            p_values, alpha=alpha, method=method
        )
        
        return reject, pvals_corrected, alpha_sidak, alpha_bonf
    
    @staticmethod
    def benjamini_hochberg(
        p_values: np.ndarray, alpha: float = 0.05
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Benjamini-Hochberg FDR correction.
        
        Args:
            p_values: Array of p-values
            alpha: FDR level
            
        Returns:
            Adjusted p-values and rejection decisions
        """
        n = len(p_values)
        sorted_indices = np.argsort(p_values)
        sorted_pvals = p_values[sorted_indices]
        
        # BH procedure
        adjusted = np.zeros(n)
        for i in range(n):
            adjusted[sorted_indices[i]] = min(
                sorted_pvals[i] * n / (i + 1), 1.0
            )
        
        # Ensure monotonicity
        for i in range(n - 2, -1, -1):
            idx = sorted_indices[i]
            next_idx = sorted_indices[i + 1]
            adjusted[idx] = min(adjusted[idx], adjusted[next_idx])
        
        reject = adjusted <= alpha
        
        return adjusted, reject
    
    @staticmethod
    def q_value(p_values: np.ndarray) -> np.ndarray:
        """
        Compute q-values (Storey's method).
        
        Args:
            p_values: Array of p-values
            
        Returns:
            Q-values
        """
        n = len(p_values)
        sorted_indices = np.argsort(p_values)
        sorted_pvals = p_values[sorted_indices]
        
        # Estimate pi0 (proportion of true nulls)
        lambdas = np.arange(0.05, 0.95, 0.05)
        pi0_estimates = []
        for lam in lambdas:
            pi0_estimates.append(
                np.sum(sorted_pvals > lam) / (n * (1 - lam))
            )
        pi0 = min(1.0, np.median(pi0_estimates))
        
        # Compute q-values
        q_values = np.zeros(n)
        for i in range(n):
            q_values[sorted_indices[i]] = min(
                pi0 * sorted_pvals[i] * n / (i + 1), 1.0
            )
        
        # Ensure monotonicity
        for i in range(n - 2, -1, -1):
            idx = sorted_indices[i]
            next_idx = sorted_indices[i + 1]
            q_values[idx] = min(q_values[idx], q_values[next_idx])
        
        return q_values


class StatisticalAnalysisPipeline:
    """
    Comprehensive statistical analysis pipeline.
    
    Performs multiple statistical tests with automatic
    test selection, effect size calculation, and multiple
    testing correction.
    """
    
    def __init__(
        self,
        # Test selection
        test: Optional[StatisticalTest] = None,
        auto_select_test: bool = True,
        normality_alpha: float = 0.05,
        
        # Multiple testing
        correction_method: MultipleTestingMethod = MultipleTestingMethod.FDR_BH,
        alpha: float = 0.05,
        
        # Effect sizes
        compute_effect_sizes: bool = True,
        effect_size_type: str = "cohens_d",
        
        # Filtering
        min_samples_per_group: int = 3,
        min_variance: float = 1e-10,
        
        # Execution
        n_jobs: int = -1,
        verbose: bool = True,
    ):
        """
        Initialize statistical analysis pipeline.
        
        Args:
            test: Specific test to use (or None for auto-selection)
            auto_select_test: Automatically select appropriate test
            normality_alpha: Alpha level for normality tests
            correction_method: Multiple testing correction method
            alpha: Significance level
            compute_effect_sizes: Whether to compute effect sizes
            effect_size_type: Type of effect size to compute
            min_samples_per_group: Minimum samples required per group
            min_variance: Minimum variance threshold
            n_jobs: Number of parallel jobs
            verbose: Verbosity flag
        """
        self.test = test
        self.auto_select_test = auto_select_test
        self.normality_alpha = normality_alpha
        self.correction_method = correction_method
        self.alpha = alpha
        self.compute_effect_sizes = compute_effect_sizes
        self.effect_size_type = effect_size_type
        self.min_samples_per_group = min_samples_per_group
        self.min_variance = min_variance
        self.n_jobs = n_jobs
        self.verbose = verbose
        
        self.results_: Optional[StatisticalAnalysisResult] = None
    
    def analyze(
        self,
        data: Union[np.ndarray, pd.DataFrame],
        groups: Union[np.ndarray, pd.Series],
        feature_names: Optional[List[str]] = None,
    ) -> StatisticalAnalysisResult:
        """
        Run statistical analysis on all features.
        
        Args:
            data: Feature matrix (samples x features)
            groups: Group labels for each sample
            feature_names: Optional feature names
            
        Returns:
            StatisticalAnalysisResult
        """
        # Convert inputs
        if isinstance(data, pd.DataFrame):
            feature_names = feature_names or data.columns.tolist()
            data = data.values
        if isinstance(groups, pd.Series):
            groups = groups.values
        
        n_samples, n_features = data.shape
        feature_names = feature_names or [f"feature_{i}" for i in range(n_features)]
        
        unique_groups = np.unique(groups)
        n_groups = len(unique_groups)
        
        if self.verbose:
            logger.info(
                f"Running statistical analysis: {n_features} features, "
                f"{n_groups} groups, {n_samples} samples"
            )
        
        # Determine test type
        test_to_use = self._select_test(data, groups, unique_groups)
        
        # Run tests
        results = []
        p_values = []
        
        with ThreadPoolExecutor(max_workers=self.n_jobs if self.n_jobs > 0 else None) as executor:
            futures = {
                executor.submit(
                    self._test_feature, 
                    data[:, i], groups, unique_groups, 
                    feature_names[i], test_to_use
                ): i
                for i in range(n_features)
            }
            
            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result is not None:
                        results.append(result)
                        p_values.append(result.p_value)
                except Exception as e:
                    logger.warning(f"Test failed: {e}")
        
        # Sort by original order
        results.sort(key=lambda r: feature_names.index(r.feature))
        p_values = np.array([r.p_value for r in results])
        
        # Multiple testing correction
        if len(p_values) > 0:
            reject, adjusted_p, _, _ = MultipleTestingCorrection.correct(
                p_values, self.correction_method, self.alpha
            )
            
            for i, result in enumerate(results):
                result.adjusted_p_value = adjusted_p[i]
                result.is_significant = reject[i]
        
        # Get significant features
        significant_features = [r.feature for r in results if r.is_significant]
        
        # Create summary DataFrame
        summary = self._create_summary(results)
        
        self.results_ = StatisticalAnalysisResult(
            results=results,
            summary=summary,
            significant_features=significant_features,
            n_tests=len(results),
            n_significant=len(significant_features),
            correction_method=self.correction_method.value,
            alpha=self.alpha,
            parameters={
                "test": test_to_use.value if test_to_use else "auto",
                "n_groups": n_groups,
                "effect_size_type": self.effect_size_type,
            }
        )
        
        if self.verbose:
            logger.info(
                f"Analysis complete: {len(significant_features)}/{len(results)} "
                f"significant features (alpha={self.alpha})"
            )
        
        return self.results_
    
    def _select_test(
        self,
        data: np.ndarray,
        groups: np.ndarray,
        unique_groups: np.ndarray,
    ) -> StatisticalTest:
        """Automatically select appropriate statistical test."""
        if self.test is not None:
            return self.test
        
        n_groups = len(unique_groups)
        
        # Sample a subset for normality testing
        sample_size = min(5000, data.shape[0] * data.shape[1])
        flat_data = data.flatten()
        if len(flat_data) > sample_size:
            sample = np.random.choice(flat_data, sample_size, replace=False)
        else:
            sample = flat_data
        
        # Test normality
        try:
            _, normality_p = shapiro(sample[:5000])
            is_normal = normality_p > self.normality_alpha
        except:
            is_normal = False
        
        # Select test based on number of groups and normality
        if n_groups == 2:
            # Test for equal variances
            g1 = data[groups == unique_groups[0]].flatten()
            g2 = data[groups == unique_groups[1]].flatten()
            try:
                _, var_p = levene(g1[:1000], g2[:1000])
                equal_var = var_p > 0.05
            except:
                equal_var = True
            
            if is_normal:
                if equal_var:
                    return StatisticalTest.TTEST_IND
                else:
                    return StatisticalTest.WELCH_TTEST
            else:
                return StatisticalTest.MANN_WHITNEY
        else:
            # Multiple groups
            if is_normal:
                return StatisticalTest.ANOVA
            else:
                return StatisticalTest.KRUSKAL_WALLIS
    
    def _test_feature(
        self,
        feature_data: np.ndarray,
        groups: np.ndarray,
        unique_groups: np.ndarray,
        feature_name: str,
        test: StatisticalTest,
    ) -> Optional[TestResult]:
        """Run statistical test for a single feature."""
        # Check variance
        if feature_data.var() < self.min_variance:
            return None
        
        # Split by groups
        group_data = [
            feature_data[groups == g] for g in unique_groups
        ]
        
        # Check sample sizes
        if any(len(g) < self.min_samples_per_group for g in group_data):
            return None
        
        # Run test
        try:
            if test == StatisticalTest.TTEST_IND:
                stat, p_value = ttest_ind(group_data[0], group_data[1])
                
            elif test == StatisticalTest.WELCH_TTEST:
                stat, p_value = ttest_ind(group_data[0], group_data[1], equal_var=False)
                
            elif test == StatisticalTest.MANN_WHITNEY:
                stat, p_value = mannwhitneyu(
                    group_data[0], group_data[1], alternative="two-sided"
                )
                
            elif test == StatisticalTest.ANOVA:
                stat, p_value = f_oneway(*group_data)
                
            elif test == StatisticalTest.KRUSKAL_WALLIS:
                stat, p_value = kruskal(*group_data)
                
            else:
                logger.warning(f"Unknown test: {test}")
                return None
                
        except Exception as e:
            logger.debug(f"Test failed for {feature_name}: {e}")
            return None
        
        # Handle NaN p-values
        if np.isnan(p_value):
            p_value = 1.0
        
        # Create result
        result = TestResult(
            feature=feature_name,
            test_name=test.value,
            statistic=float(stat),
            p_value=float(p_value),
        )
        
        # Add group statistics (for two groups)
        if len(unique_groups) == 2:
            result.mean_group1 = float(group_data[0].mean())
            result.mean_group2 = float(group_data[1].mean())
            result.std_group1 = float(group_data[0].std())
            result.std_group2 = float(group_data[1].std())
            result.n_group1 = len(group_data[0])
            result.n_group2 = len(group_data[1])
            
            # Fold change
            if result.mean_group1 > 0:
                result.fold_change = result.mean_group2 / result.mean_group1
                if result.fold_change > 0:
                    result.log2_fold_change = np.log2(result.fold_change)
            
            # Direction
            if result.mean_group2 > result.mean_group1:
                result.direction = "up"
            elif result.mean_group2 < result.mean_group1:
                result.direction = "down"
        
        # Effect size
        if self.compute_effect_sizes:
            result.effect_size, result.effect_size_type = self._compute_effect_size(
                group_data, test
            )
        
        return result
    
    def _compute_effect_size(
        self,
        group_data: List[np.ndarray],
        test: StatisticalTest,
    ) -> Tuple[Optional[float], Optional[str]]:
        """Compute effect size for test result."""
        try:
            if len(group_data) == 2:
                if self.effect_size_type == "cohens_d":
                    d, _ = EffectSizeCalculator.cohens_d(group_data[0], group_data[1])
                    return d, "cohens_d"
                    
                elif self.effect_size_type == "hedges_g":
                    g, _ = EffectSizeCalculator.hedges_g(group_data[0], group_data[1])
                    return g, "hedges_g"
                    
                elif self.effect_size_type == "cliffs_delta":
                    delta, _ = EffectSizeCalculator.cliffs_delta(
                        group_data[0], group_data[1]
                    )
                    return delta, "cliffs_delta"
                    
            else:
                # Multiple groups - use eta-squared
                eta_sq = EffectSizeCalculator.eta_squared(group_data)
                return eta_sq, "eta_squared"
                
        except Exception as e:
            logger.debug(f"Effect size computation failed: {e}")
        
        return None, None
    
    def _create_summary(self, results: List[TestResult]) -> pd.DataFrame:
        """Create summary DataFrame from results."""
        data = []
        for r in results:
            row = {
                "feature": r.feature,
                "test": r.test_name,
                "statistic": r.statistic,
                "p_value": r.p_value,
                "adjusted_p_value": r.adjusted_p_value,
                "is_significant": r.is_significant,
                "effect_size": r.effect_size,
                "effect_size_type": r.effect_size_type,
                "mean_group1": r.mean_group1,
                "mean_group2": r.mean_group2,
                "log2_fold_change": r.log2_fold_change,
                "direction": r.direction,
            }
            data.append(row)
        
        df = pd.DataFrame(data)
        df = df.sort_values("p_value")
        return df
    
    def get_significant_features(
        self, 
        adjusted: bool = True,
        alpha: Optional[float] = None
    ) -> List[str]:
        """Get list of significant features."""
        if self.results_ is None:
            raise ValueError("Analysis not run")
        
        alpha = alpha or self.alpha
        
        if adjusted:
            return [
                r.feature for r in self.results_.results
                if r.adjusted_p_value is not None and r.adjusted_p_value < alpha
            ]
        else:
            return [
                r.feature for r in self.results_.results
                if r.p_value < alpha
            ]
    
    def get_volcano_plot_data(self) -> pd.DataFrame:
        """Get data formatted for volcano plot."""
        if self.results_ is None:
            raise ValueError("Analysis not run")
        
        df = self.results_.summary.copy()
        df["neg_log10_p"] = -np.log10(df["p_value"].clip(lower=1e-300))
        df["neg_log10_adj_p"] = -np.log10(df["adjusted_p_value"].clip(lower=1e-300))
        
        return df[["feature", "log2_fold_change", "neg_log10_p", 
                   "neg_log10_adj_p", "is_significant", "direction"]]


def differential_expression_analysis(
    expression_matrix: pd.DataFrame,
    condition_labels: pd.Series,
    control_label: str = "control",
    case_label: str = "case",
    method: str = "auto",
    fdr_threshold: float = 0.05,
    log2fc_threshold: float = 1.0,
) -> pd.DataFrame:
    """
    Perform differential expression analysis.
    
    Args:
        expression_matrix: Gene expression matrix (genes x samples)
        condition_labels: Sample condition labels
        control_label: Label for control group
        case_label: Label for case group
        method: Statistical method ('ttest', 'wilcoxon', 'auto')
        fdr_threshold: FDR significance threshold
        log2fc_threshold: Log2 fold change threshold
        
    Returns:
        DataFrame with differential expression results
    """
    # Input is genes x samples. Check if we need to transpose by checking
    # if column names match condition labels (samples should be columns)
    common_samples = expression_matrix.columns.intersection(condition_labels.index)
    if len(common_samples) == 0:
        # Try with index (matrix might be samples x genes)
        common_samples = expression_matrix.index.intersection(condition_labels.index)
        if len(common_samples) > 0:
            expression_matrix = expression_matrix.T
            common_samples = expression_matrix.columns.intersection(condition_labels.index)
    
    # Align samples
    expression_matrix = expression_matrix[common_samples]
    condition_labels = condition_labels[common_samples]
    
    # Run statistical analysis
    pipeline = StatisticalAnalysisPipeline(
        test=None if method == "auto" else (
            StatisticalTest.TTEST_IND if method == "ttest" else StatisticalTest.MANN_WHITNEY
        ),
        correction_method=MultipleTestingMethod.FDR_BH,
        alpha=fdr_threshold,
    )
    
    # Transpose back for analysis (features as columns)
    results = pipeline.analyze(
        expression_matrix.T,
        condition_labels.values,
        feature_names=expression_matrix.index.tolist()
    )
    
    # Add DEG classification
    summary = results.summary.copy()
    summary["is_deg"] = (
        (summary["adjusted_p_value"] < fdr_threshold) &
        (summary["log2_fold_change"].abs() > log2fc_threshold)
    )
    summary["deg_class"] = "not_significant"
    summary.loc[
        summary["is_deg"] & (summary["log2_fold_change"] > log2fc_threshold),
        "deg_class"
    ] = "upregulated"
    summary.loc[
        summary["is_deg"] & (summary["log2_fold_change"] < -log2fc_threshold),
        "deg_class"
    ] = "downregulated"
    
    return summary

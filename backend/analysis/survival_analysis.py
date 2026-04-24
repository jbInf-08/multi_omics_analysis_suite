"""
Survival Analysis Module
========================

Comprehensive survival analysis including:
- Kaplan-Meier estimation
- Cox Proportional Hazards regression
- Log-rank tests
- Restricted mean survival time
- Concordance index calculation
- Survival curves visualization data
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field
from enum import Enum
import logging
import warnings

# Suppress lifelines warnings
warnings.filterwarnings("ignore", category=RuntimeWarning)

from lifelines import (
    KaplanMeierFitter,
    CoxPHFitter,
    WeibullAFTFitter,
    LogNormalAFTFitter,
    LogLogisticAFTFitter,
    NelsonAalenFitter,
)
from lifelines.statistics import (
    logrank_test,
    multivariate_logrank_test,
    pairwise_logrank_test,
)
from lifelines.utils import concordance_index, restricted_mean_survival_time
from lifelines.plotting import add_at_risk_counts

logger = logging.getLogger(__name__)


class SurvivalModel(str, Enum):
    """Available survival models."""
    KAPLAN_MEIER = "kaplan_meier"
    COX_PH = "cox_ph"
    WEIBULL_AFT = "weibull_aft"
    LOGNORMAL_AFT = "lognormal_aft"
    LOGLOGISTIC_AFT = "loglogistic_aft"
    NELSON_AALEN = "nelson_aalen"


@dataclass
class KaplanMeierResult:
    """Results from Kaplan-Meier analysis."""
    group: str
    n_subjects: int
    n_events: int
    median_survival: Optional[float]
    median_ci_lower: Optional[float]
    median_ci_upper: Optional[float]
    survival_function: pd.DataFrame
    confidence_interval: pd.DataFrame
    at_risk_counts: pd.Series
    restricted_mean: Optional[float] = None
    restricted_mean_se: Optional[float] = None


@dataclass
class CoxPHResult:
    """Results from Cox Proportional Hazards analysis."""
    covariate: str
    coefficient: float
    hazard_ratio: float
    hr_ci_lower: float
    hr_ci_upper: float
    se: float
    z_score: float
    p_value: float
    is_significant: bool


@dataclass
class LogRankResult:
    """Results from log-rank test."""
    test_statistic: float
    p_value: float
    degrees_of_freedom: int
    is_significant: bool
    group_comparisons: Optional[Dict[str, float]] = None


@dataclass
class SurvivalAnalysisResult:
    """Comprehensive survival analysis results."""
    km_results: Dict[str, KaplanMeierResult]
    cox_results: Optional[List[CoxPHResult]]
    logrank_result: Optional[LogRankResult]
    concordance_index: Optional[float]
    concordance_ci: Optional[Tuple[float, float]]
    n_total: int
    n_events: int
    median_followup: float
    parameters: Dict[str, Any]


class KaplanMeierEstimator:
    """
    Kaplan-Meier survival estimation.
    
    Estimates survival function from censored data
    with confidence intervals and at-risk counts.
    """
    
    def __init__(
        self,
        confidence_level: float = 0.95,
        label: str = "KM_estimate",
    ):
        """
        Initialize Kaplan-Meier estimator.
        
        Args:
            confidence_level: Confidence level for intervals
            label: Label for the estimate
        """
        self.confidence_level = confidence_level
        self.label = label
        self.fitter_ = KaplanMeierFitter()
        self.result_: Optional[KaplanMeierResult] = None
    
    def fit(
        self,
        durations: np.ndarray,
        events: np.ndarray,
        label: Optional[str] = None,
        timeline: Optional[np.ndarray] = None,
    ) -> "KaplanMeierEstimator":
        """
        Fit Kaplan-Meier estimator.
        
        Args:
            durations: Observed durations (time to event or censoring)
            events: Event indicators (1=event, 0=censored)
            label: Optional label override
            timeline: Optional timeline for estimation
            
        Returns:
            Fitted KaplanMeierEstimator
        """
        label = label or self.label
        
        self.fitter_.fit(
            durations,
            event_observed=events,
            label=label,
            timeline=timeline,
            alpha=1 - self.confidence_level,
        )
        
        # Extract results
        median = self.fitter_.median_survival_time_
        median_ci = self.fitter_.confidence_interval_median_survival_time_
        
        self.result_ = KaplanMeierResult(
            group=label,
            n_subjects=len(durations),
            n_events=int(events.sum()),
            median_survival=median if not np.isinf(median) else None,
            median_ci_lower=median_ci.iloc[0, 0] if not median_ci.empty else None,
            median_ci_upper=median_ci.iloc[0, 1] if not median_ci.empty else None,
            survival_function=self.fitter_.survival_function_,
            confidence_interval=self.fitter_.confidence_interval_survival_function_,
            at_risk_counts=self.fitter_.event_table["at_risk"],
        )
        
        # Restricted mean survival time
        try:
            rmst = restricted_mean_survival_time(self.fitter_)
            self.result_.restricted_mean = rmst
        except:
            pass
        
        return self
    
    def predict(self, times: np.ndarray) -> np.ndarray:
        """Predict survival probability at given times."""
        return self.fitter_.predict(times).values
    
    def get_survival_function(self) -> pd.DataFrame:
        """Get survival function as DataFrame."""
        return self.fitter_.survival_function_
    
    def get_confidence_intervals(self) -> pd.DataFrame:
        """Get confidence intervals for survival function."""
        return self.fitter_.confidence_interval_survival_function_
    
    def get_plot_data(self) -> pd.DataFrame:
        """Get data formatted for plotting."""
        sf = self.fitter_.survival_function_
        ci = self.fitter_.confidence_interval_survival_function_
        
        df = pd.DataFrame({
            "time": sf.index,
            "survival": sf.iloc[:, 0].values,
            "ci_lower": ci.iloc[:, 0].values,
            "ci_upper": ci.iloc[:, 1].values,
            "group": self.result_.group if self.result_ else self.label,
        })
        
        return df


class CoxProportionalHazards:
    """
    Cox Proportional Hazards regression.
    
    Models hazard as a function of covariates with
    semi-parametric baseline hazard.
    """
    
    def __init__(
        self,
        penalizer: float = 0.0,
        l1_ratio: float = 0.0,
        strata: Optional[List[str]] = None,
        robust: bool = False,
        cluster_col: Optional[str] = None,
    ):
        """
        Initialize Cox PH model.
        
        Args:
            penalizer: Regularization penalty strength
            l1_ratio: L1 vs L2 penalty ratio (0=L2, 1=L1)
            strata: Stratification columns
            robust: Use robust standard errors
            cluster_col: Column for clustered standard errors
        """
        self.penalizer = penalizer
        self.l1_ratio = l1_ratio
        self.strata = strata
        self.robust = robust
        self.cluster_col = cluster_col
        
        self.fitter_ = CoxPHFitter(
            penalizer=penalizer,
            l1_ratio=l1_ratio,
        )
        self.results_: Optional[List[CoxPHResult]] = None
    
    def fit(
        self,
        data: pd.DataFrame,
        duration_col: str,
        event_col: str,
        covariates: Optional[List[str]] = None,
        show_progress: bool = False,
    ) -> "CoxProportionalHazards":
        """
        Fit Cox PH model.
        
        Args:
            data: DataFrame with survival data
            duration_col: Name of duration column
            event_col: Name of event indicator column
            covariates: Columns to use as covariates (None = all others)
            show_progress: Show fitting progress
            
        Returns:
            Fitted CoxProportionalHazards
        """
        # Prepare data
        if covariates is not None:
            cols = [duration_col, event_col] + covariates
            if self.strata:
                cols += self.strata
            data = data[cols].copy()
        
        # Fit model
        self.fitter_.fit(
            data,
            duration_col=duration_col,
            event_col=event_col,
            strata=self.strata,
            robust=self.robust,
            cluster_col=self.cluster_col,
            show_progress=show_progress,
        )
        
        # Extract results
        summary = self.fitter_.summary
        self.results_ = []
        
        for covariate in summary.index:
            result = CoxPHResult(
                covariate=covariate,
                coefficient=summary.loc[covariate, "coef"],
                hazard_ratio=summary.loc[covariate, "exp(coef)"],
                hr_ci_lower=summary.loc[covariate, "exp(coef) lower 95%"],
                hr_ci_upper=summary.loc[covariate, "exp(coef) upper 95%"],
                se=summary.loc[covariate, "se(coef)"],
                z_score=summary.loc[covariate, "z"],
                p_value=summary.loc[covariate, "p"],
                is_significant=summary.loc[covariate, "p"] < 0.05,
            )
            self.results_.append(result)
        
        return self
    
    def predict_hazard(self, data: pd.DataFrame) -> pd.DataFrame:
        """Predict hazard for new data."""
        return self.fitter_.predict_partial_hazard(data)
    
    def predict_survival_function(
        self, data: pd.DataFrame, times: Optional[np.ndarray] = None
    ) -> pd.DataFrame:
        """Predict survival function for new data."""
        return self.fitter_.predict_survival_function(data, times=times)
    
    def predict_median(self, data: pd.DataFrame) -> pd.Series:
        """Predict median survival time."""
        return self.fitter_.predict_median(data)
    
    def concordance_index(self) -> float:
        """Get concordance index."""
        return self.fitter_.concordance_index_
    
    def check_assumptions(self) -> pd.DataFrame:
        """Check proportional hazards assumption."""
        return self.fitter_.check_assumptions(self.fitter_.training_frame, show_plots=False)
    
    def get_summary(self) -> pd.DataFrame:
        """Get model summary."""
        return self.fitter_.summary
    
    def get_baseline_hazard(self) -> pd.DataFrame:
        """Get baseline hazard function."""
        return self.fitter_.baseline_hazard_
    
    def get_baseline_survival(self) -> pd.DataFrame:
        """Get baseline survival function."""
        return self.fitter_.baseline_survival_


def logrank_test_comparison(
    durations_a: np.ndarray,
    events_a: np.ndarray,
    durations_b: np.ndarray,
    events_b: np.ndarray,
    alpha: float = 0.05,
) -> LogRankResult:
    """
    Perform log-rank test between two groups.
    
    Args:
        durations_a: Durations for group A
        events_a: Events for group A
        durations_b: Durations for group B
        events_b: Events for group B
        alpha: Significance level
        
    Returns:
        LogRankResult
    """
    result = logrank_test(durations_a, durations_b, events_a, events_b)
    
    return LogRankResult(
        test_statistic=result.test_statistic,
        p_value=result.p_value,
        degrees_of_freedom=1,
        is_significant=result.p_value < alpha,
    )


def multivariate_logrank_comparison(
    durations: np.ndarray,
    events: np.ndarray,
    groups: np.ndarray,
    alpha: float = 0.05,
) -> LogRankResult:
    """
    Perform multivariate log-rank test across multiple groups.
    
    Args:
        durations: All durations
        events: All event indicators
        groups: Group labels
        alpha: Significance level
        
    Returns:
        LogRankResult with pairwise comparisons
    """
    result = multivariate_logrank_test(durations, groups, events)
    
    # Pairwise comparisons
    unique_groups = np.unique(groups)
    pairwise = {}
    
    if len(unique_groups) > 2:
        for i, g1 in enumerate(unique_groups):
            for g2 in unique_groups[i+1:]:
                mask1 = groups == g1
                mask2 = groups == g2
                
                pw_result = logrank_test(
                    durations[mask1], durations[mask2],
                    events[mask1], events[mask2]
                )
                pairwise[f"{g1}_vs_{g2}"] = pw_result.p_value
    
    return LogRankResult(
        test_statistic=result.test_statistic,
        p_value=result.p_value,
        degrees_of_freedom=len(unique_groups) - 1,
        is_significant=result.p_value < alpha,
        group_comparisons=pairwise if pairwise else None,
    )


class SurvivalAnalysisPipeline:
    """
    Comprehensive survival analysis pipeline.
    
    Integrates Kaplan-Meier estimation, Cox regression,
    and log-rank tests with automatic model selection.
    """
    
    def __init__(
        self,
        # Analysis options
        run_km: bool = True,
        run_cox: bool = True,
        run_logrank: bool = True,
        
        # Model parameters
        confidence_level: float = 0.95,
        cox_penalizer: float = 0.0,
        
        # Significance
        alpha: float = 0.05,
        
        # Output
        verbose: bool = True,
    ):
        """
        Initialize survival analysis pipeline.
        
        Args:
            run_km: Run Kaplan-Meier analysis
            run_cox: Run Cox PH regression
            run_logrank: Run log-rank tests
            confidence_level: Confidence level for intervals
            cox_penalizer: Regularization for Cox model
            alpha: Significance level
            verbose: Verbosity flag
        """
        self.run_km = run_km
        self.run_cox = run_cox
        self.run_logrank = run_logrank
        self.confidence_level = confidence_level
        self.cox_penalizer = cox_penalizer
        self.alpha = alpha
        self.verbose = verbose
        
        self.results_: Optional[SurvivalAnalysisResult] = None
    
    def analyze(
        self,
        data: pd.DataFrame,
        duration_col: str,
        event_col: str,
        group_col: Optional[str] = None,
        covariates: Optional[List[str]] = None,
    ) -> SurvivalAnalysisResult:
        """
        Run comprehensive survival analysis.
        
        Args:
            data: DataFrame with survival data
            duration_col: Name of duration column
            event_col: Name of event column
            group_col: Optional grouping column for KM/logrank
            covariates: Covariates for Cox model
            
        Returns:
            SurvivalAnalysisResult
        """
        if self.verbose:
            logger.info(f"Running survival analysis on {len(data)} subjects")
        
        durations = data[duration_col].values
        events = data[event_col].values
        
        # Basic statistics
        n_total = len(data)
        n_events = int(events.sum())
        median_followup = float(np.median(durations))
        
        km_results = {}
        cox_results = None
        logrank_result = None
        c_index = None
        c_index_ci = None
        
        # Kaplan-Meier analysis
        if self.run_km:
            if group_col is not None:
                groups = data[group_col].unique()
                for group in groups:
                    mask = data[group_col] == group
                    km = KaplanMeierEstimator(
                        confidence_level=self.confidence_level,
                        label=str(group),
                    )
                    km.fit(durations[mask], events[mask])
                    km_results[str(group)] = km.result_
            else:
                km = KaplanMeierEstimator(
                    confidence_level=self.confidence_level,
                    label="Overall",
                )
                km.fit(durations, events)
                km_results["Overall"] = km.result_
        
        # Log-rank test
        if self.run_logrank and group_col is not None:
            groups = data[group_col].values
            logrank_result = multivariate_logrank_comparison(
                durations, events, groups, self.alpha
            )
        
        # Cox regression
        if self.run_cox and covariates:
            try:
                cox = CoxProportionalHazards(penalizer=self.cox_penalizer)
                cox.fit(data, duration_col, event_col, covariates)
                cox_results = cox.results_
                c_index = cox.concordance_index()
            except Exception as e:
                logger.warning(f"Cox regression failed: {e}")
        
        self.results_ = SurvivalAnalysisResult(
            km_results=km_results,
            cox_results=cox_results,
            logrank_result=logrank_result,
            concordance_index=c_index,
            concordance_ci=c_index_ci,
            n_total=n_total,
            n_events=n_events,
            median_followup=median_followup,
            parameters={
                "confidence_level": self.confidence_level,
                "alpha": self.alpha,
                "cox_penalizer": self.cox_penalizer,
            }
        )
        
        if self.verbose:
            logger.info(
                f"Survival analysis complete: {n_events}/{n_total} events, "
                f"median followup: {median_followup:.1f}"
            )
            if logrank_result:
                logger.info(
                    f"Log-rank test: p={logrank_result.p_value:.4f} "
                    f"({'significant' if logrank_result.is_significant else 'not significant'})"
                )
        
        return self.results_
    
    def get_km_plot_data(self) -> pd.DataFrame:
        """Get Kaplan-Meier data for plotting."""
        if self.results_ is None:
            raise ValueError("Analysis not run")
        
        dfs = []
        for group, result in self.results_.km_results.items():
            df = pd.DataFrame({
                "time": result.survival_function.index,
                "survival": result.survival_function.iloc[:, 0].values,
                "ci_lower": result.confidence_interval.iloc[:, 0].values,
                "ci_upper": result.confidence_interval.iloc[:, 1].values,
                "group": group,
            })
            dfs.append(df)
        
        return pd.concat(dfs, ignore_index=True)
    
    def get_cox_summary(self) -> pd.DataFrame:
        """Get Cox regression summary as DataFrame."""
        if self.results_ is None or self.results_.cox_results is None:
            raise ValueError("Cox analysis not available")
        
        data = []
        for r in self.results_.cox_results:
            data.append({
                "covariate": r.covariate,
                "coefficient": r.coefficient,
                "hazard_ratio": r.hazard_ratio,
                "hr_ci_lower": r.hr_ci_lower,
                "hr_ci_upper": r.hr_ci_upper,
                "se": r.se,
                "z_score": r.z_score,
                "p_value": r.p_value,
                "significant": r.is_significant,
            })
        
        return pd.DataFrame(data)


def biomarker_survival_analysis(
    data: pd.DataFrame,
    duration_col: str,
    event_col: str,
    biomarker_col: str,
    cutoff: Optional[float] = None,
    cutoff_method: str = "median",
    n_groups: int = 2,
) -> Dict[str, Any]:
    """
    Analyze survival stratified by biomarker expression.
    
    Args:
        data: DataFrame with survival and biomarker data
        duration_col: Duration column name
        event_col: Event column name
        biomarker_col: Biomarker column name
        cutoff: Fixed cutoff value (None for automatic)
        cutoff_method: Method for automatic cutoff ('median', 'mean', 'tertile', 'quartile')
        n_groups: Number of groups (2, 3, or 4)
        
    Returns:
        Analysis results dictionary
    """
    biomarker_values = data[biomarker_col].values
    
    # Determine cutoffs
    if cutoff is not None:
        groups = np.where(biomarker_values >= cutoff, "High", "Low")
    elif cutoff_method == "median":
        cutoff = np.median(biomarker_values)
        groups = np.where(biomarker_values >= cutoff, "High", "Low")
    elif cutoff_method == "mean":
        cutoff = np.mean(biomarker_values)
        groups = np.where(biomarker_values >= cutoff, "High", "Low")
    elif cutoff_method == "tertile":
        tertiles = np.percentile(biomarker_values, [33.33, 66.67])
        groups = np.select(
            [biomarker_values < tertiles[0],
             biomarker_values < tertiles[1],
             biomarker_values >= tertiles[1]],
            ["Low", "Medium", "High"]
        )
    elif cutoff_method == "quartile":
        quartiles = np.percentile(biomarker_values, [25, 50, 75])
        groups = np.select(
            [biomarker_values < quartiles[0],
             biomarker_values < quartiles[1],
             biomarker_values < quartiles[2],
             biomarker_values >= quartiles[2]],
            ["Q1", "Q2", "Q3", "Q4"]
        )
    else:
        raise ValueError(f"Unknown cutoff method: {cutoff_method}")
    
    # Add group column
    data_with_groups = data.copy()
    data_with_groups["biomarker_group"] = groups
    
    # Run survival analysis
    pipeline = SurvivalAnalysisPipeline(
        run_km=True,
        run_cox=True,
        run_logrank=True,
    )
    
    results = pipeline.analyze(
        data_with_groups,
        duration_col,
        event_col,
        group_col="biomarker_group",
        covariates=[biomarker_col],
    )
    
    # Compile results
    output = {
        "biomarker": biomarker_col,
        "cutoff": cutoff if cutoff is not None else np.median(biomarker_values),
        "cutoff_method": cutoff_method,
        "n_groups": len(np.unique(groups)),
        "km_results": results.km_results,
        "logrank_p_value": results.logrank_result.p_value if results.logrank_result else None,
        "logrank_significant": results.logrank_result.is_significant if results.logrank_result else None,
        "cox_hazard_ratio": results.cox_results[0].hazard_ratio if results.cox_results else None,
        "cox_p_value": results.cox_results[0].p_value if results.cox_results else None,
        "concordance_index": results.concordance_index,
        "plot_data": pipeline.get_km_plot_data(),
    }
    
    return output

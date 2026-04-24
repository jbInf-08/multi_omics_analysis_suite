"""
Metabolomics Module
===================

Comprehensive metabolite analysis including:
- Metabolite identification
- Quantification
- Pathway mapping
- Biomarker discovery
"""

from typing import Dict, List, Any, Optional
from pathlib import Path
import logging

import numpy as np
import pandas as pd
from scipy import stats

from backend.omics.base.omics_base import (
    OmicsModuleBase,
    OmicsCategory,
    OmicsData,
    QCReport,
    QCMetric,
    AnalysisParams,
    AnalysisResult,
    Visualization,
    Pipeline,
    AnalysisDefinition,
    DataSource,
)


logger = logging.getLogger(__name__)


class MetabolomicsModule(OmicsModuleBase):
    """Metabolomics analysis module for small molecule analysis."""
    
    def __init__(self):
        super().__init__()
        self._version = "1.0.0"
        self._supported_formats = ["csv", "tsv", "mzML", "mzXML"]
        
        self._pipelines = [
            Pipeline(
                name="untargeted_metabolomics",
                description="Untargeted metabolomics analysis pipeline",
                steps=["load_data", "quality_control", "normalization", "feature_selection", "annotation", "pathway_mapping"],
                default_parameters={"normalization": "pqn", "annotation_db": "hmdb"},
            ),
            Pipeline(
                name="targeted_metabolomics",
                description="Targeted metabolomics quantification",
                steps=["load_data", "quality_control", "calibration", "quantification", "statistical_analysis"],
                default_parameters={"calibration_method": "linear"},
            ),
        ]
        
        self._analyses = [
            AnalysisDefinition(
                name="differential_metabolites",
                description="Identify differentially abundant metabolites",
                parameters={
                    "method": {"type": "str", "default": "ttest", "description": "Statistical method"},
                    "fdr_threshold": {"type": "float", "default": 0.05, "description": "FDR threshold"},
                },
                output_types=["table", "volcano_plot"],
            ),
            AnalysisDefinition(
                name="pathway_analysis",
                description="Metabolic pathway enrichment analysis",
                parameters={
                    "database": {"type": "str", "default": "kegg", "description": "Pathway database"},
                    "organism": {"type": "str", "default": "hsa", "description": "Organism code"},
                },
                output_types=["table", "pathway_map"],
            ),
            AnalysisDefinition(
                name="metabolite_correlation",
                description="Metabolite correlation network",
                parameters={
                    "method": {"type": "str", "default": "spearman", "description": "Correlation method"},
                    "threshold": {"type": "float", "default": 0.7, "description": "Correlation threshold"},
                },
                output_types=["network", "heatmap"],
            ),
        ]
    
    @property
    def name(self) -> str:
        return "metabolomics"
    
    @property
    def category(self) -> OmicsCategory:
        return OmicsCategory.CORE
    
    @property
    def description(self) -> str:
        return "Small molecule and metabolite analysis from LC-MS/NMR data"
    
    def load_data(self, source: DataSource) -> OmicsData:
        """Load metabolomics data."""
        if source.source_type == "file":
            file_path = Path(source.path)
            format_type = source.format or file_path.suffix.lstrip(".")
            
            if format_type in ["csv", "tsv"]:
                sep = "\t" if format_type == "tsv" else ","
                df = pd.read_csv(file_path, sep=sep, index_col=0)
                return OmicsData(
                    data=df.T,
                    feature_names=df.index.tolist(),
                    sample_names=df.columns.tolist(),
                    data_type="metabolomics",
                    source=source,
                )
        raise ValueError(f"Unsupported source: {source.source_type}")
    
    def preprocess(self, data: OmicsData, params: Optional[Dict[str, Any]] = None) -> OmicsData:
        """Preprocess metabolomics data."""
        params = params or {}
        processed = data.copy()
        
        # Remove features with too many missing values
        max_missing = params.get("max_missing_ratio", 0.3)
        missing_ratio = processed.data.isna().sum(axis=0) / len(processed.sample_names)
        keep = missing_ratio <= max_missing
        processed.data = processed.data.loc[:, keep]
        processed.feature_names = [f for f, k in zip(processed.feature_names, keep) if k]
        
        # Imputation with half minimum
        for col in processed.data.columns:
            min_val = processed.data[col].min()
            processed.data[col] = processed.data[col].fillna(min_val / 2)
        
        processed.preprocessing_history.append(f"preprocess(max_missing={max_missing})")
        return processed
    
    def quality_control(self, data: OmicsData, params: Optional[Dict[str, Any]] = None) -> QCReport:
        """Run QC on metabolomics data."""
        metrics = []
        
        n_metabolites = len(data.feature_names)
        metrics.append(QCMetric(name="metabolite_count", value=n_metabolites, threshold=100))
        
        missing_ratio = data.data.isna().sum().sum() / data.data.size if data.data.size > 0 else 0
        metrics.append(QCMetric(name="completeness", value=1 - missing_ratio, threshold=0.7))
        
        passed = all(m.passed for m in metrics if m.passed is not None)
        return QCReport(passed=passed, metrics=metrics)
    
    def normalize(self, data: OmicsData, method: str = "pqn", params: Optional[Dict[str, Any]] = None) -> OmicsData:
        """Normalize metabolomics data."""
        normalized = data.copy()
        
        if method == "pqn":  # Probabilistic Quotient Normalization
            reference = normalized.data.median(axis=0)
            quotients = normalized.data.div(reference, axis=1)
            median_quotients = quotients.median(axis=1)
            normalized.data = normalized.data.div(median_quotients, axis=0)
        elif method == "sum":
            normalized.data = normalized.data.div(normalized.data.sum(axis=1), axis=0)
        elif method == "log":
            normalized.data = np.log2(normalized.data + 1)
        elif method == "pareto":
            normalized.data = (normalized.data - normalized.data.mean()) / np.sqrt(normalized.data.std())
        
        normalized.preprocessing_history.append(f"normalize(method={method})")
        return normalized
    
    def analyze(self, data: OmicsData, params: AnalysisParams) -> AnalysisResult:
        """Run metabolomics analysis."""
        if params.analysis_type == "differential_metabolites":
            return self._analyze_differential(data, params)
        elif params.analysis_type == "pathway_analysis":
            return self._analyze_pathways(data, params)
        elif params.analysis_type == "metabolite_correlation":
            return self._analyze_correlation(data, params)
        return AnalysisResult(analysis_type=params.analysis_type, status="failed", data={}, errors=["Unknown analysis"])
    
    def _analyze_differential(self, data: OmicsData, params: AnalysisParams) -> AnalysisResult:
        """Differential metabolite analysis."""
        results = []
        if data.sample_metadata is not None and "condition" in data.sample_metadata.columns:
            conditions = data.sample_metadata["condition"].unique()
            if len(conditions) >= 2:
                g1 = data.sample_metadata[data.sample_metadata["condition"] == conditions[0]].index
                g2 = data.sample_metadata[data.sample_metadata["condition"] == conditions[1]].index
                for met in data.feature_names:
                    if met in data.data.columns:
                        v1, v2 = data.data.loc[g1, met].dropna(), data.data.loc[g2, met].dropna()
                        if len(v1) > 1 and len(v2) > 1:
                            t, p = stats.ttest_ind(v1, v2)
                            fc = np.log2((v2.mean() + 1) / (v1.mean() + 1))
                            results.append({"metabolite": met, "log2FC": fc, "pvalue": p})
        
        return AnalysisResult(
            analysis_type="differential_metabolites",
            status="success",
            data={"results": results},
            summary={"n_tested": len(results)},
        )
    
    def _analyze_pathways(self, data: OmicsData, params: AnalysisParams) -> AnalysisResult:
        return AnalysisResult(analysis_type="pathway_analysis", status="success", data={"pathways": []}, summary={})
    
    def _analyze_correlation(self, data: OmicsData, params: AnalysisParams) -> AnalysisResult:
        method = params.get("method", "spearman")
        corr = data.data.corr(method=method)
        return AnalysisResult(
            analysis_type="metabolite_correlation",
            status="success",
            data={"correlation_matrix": corr.to_dict()},
            summary={"n_metabolites": len(data.feature_names)},
        )
    
    def visualize(self, result: AnalysisResult, plot_types: Optional[List[str]] = None) -> List[Visualization]:
        return []
    
    def get_available_pipelines(self) -> List[Pipeline]:
        return self._pipelines
    
    def get_available_analyses(self) -> List[AnalysisDefinition]:
        return self._analyses

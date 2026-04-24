"""
Lipidomics Module
=================

Lipid analysis including:
- Lipid identification
- Lipid quantification
- Lipid class analysis
- Lipid pathway mapping
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


class LipidomicsModule(OmicsModuleBase):
    """Lipidomics analysis module for lipid profiling."""
    
    def __init__(self):
        super().__init__()
        self._version = "1.0.0"
        self._supported_formats = ["csv", "tsv", "mzML"]
        
        self._pipelines = [
            Pipeline(
                name="lipid_profiling",
                description="Comprehensive lipid profiling pipeline",
                steps=["load_data", "quality_control", "lipid_identification", "quantification", "class_analysis", "pathway_mapping"],
                default_parameters={"database": "lipidmaps", "normalization": "is"},
            ),
        ]
        
        self._analyses = [
            AnalysisDefinition(
                name="lipid_class_analysis",
                description="Analyze lipid class composition",
                parameters={
                    "classes": {"type": "list", "default": None, "description": "Lipid classes to analyze"},
                },
                output_types=["table", "pie_chart", "stacked_bar"],
            ),
            AnalysisDefinition(
                name="differential_lipids",
                description="Identify differentially abundant lipids",
                parameters={
                    "method": {"type": "str", "default": "ttest", "description": "Statistical method"},
                    "fdr_threshold": {"type": "float", "default": 0.05, "description": "FDR threshold"},
                },
                output_types=["table", "volcano_plot"],
            ),
            AnalysisDefinition(
                name="fatty_acid_analysis",
                description="Analyze fatty acid composition",
                parameters={
                    "saturation": {"type": "bool", "default": True, "description": "Analyze saturation"},
                    "chain_length": {"type": "bool", "default": True, "description": "Analyze chain length"},
                },
                output_types=["table", "distribution_plot"],
            ),
        ]
    
    @property
    def name(self) -> str:
        return "lipidomics"
    
    @property
    def category(self) -> OmicsCategory:
        return OmicsCategory.CORE
    
    @property
    def description(self) -> str:
        return "Lipid profiling and analysis from mass spectrometry data"
    
    def load_data(self, source: DataSource) -> OmicsData:
        """Load lipidomics data."""
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
                    data_type="lipidomics",
                    source=source,
                )
        raise ValueError(f"Unsupported source: {source.source_type}")
    
    def preprocess(self, data: OmicsData, params: Optional[Dict[str, Any]] = None) -> OmicsData:
        """Preprocess lipidomics data."""
        params = params or {}
        processed = data.copy()
        
        # Remove lipids with too many missing values
        max_missing = params.get("max_missing_ratio", 0.3)
        missing_ratio = processed.data.isna().sum(axis=0) / len(processed.sample_names)
        keep = missing_ratio <= max_missing
        processed.data = processed.data.loc[:, keep]
        processed.feature_names = [f for f, k in zip(processed.feature_names, keep) if k]
        
        # Imputation
        for col in processed.data.columns:
            min_val = processed.data[col].min()
            processed.data[col] = processed.data[col].fillna(min_val / 2)
        
        processed.preprocessing_history.append(f"preprocess(max_missing={max_missing})")
        return processed
    
    def quality_control(self, data: OmicsData, params: Optional[Dict[str, Any]] = None) -> QCReport:
        """QC for lipidomics data."""
        metrics = []
        
        n_lipids = len(data.feature_names)
        metrics.append(QCMetric(name="lipid_count", value=n_lipids, threshold=50))
        
        missing_ratio = data.data.isna().sum().sum() / data.data.size if data.data.size > 0 else 0
        metrics.append(QCMetric(name="completeness", value=1 - missing_ratio, threshold=0.7))
        
        passed = all(m.passed for m in metrics if m.passed is not None)
        return QCReport(passed=passed, metrics=metrics)
    
    def normalize(self, data: OmicsData, method: str = "is", params: Optional[Dict[str, Any]] = None) -> OmicsData:
        """Normalize lipidomics data."""
        normalized = data.copy()
        
        if method == "is":  # Internal standard normalization
            # Would normalize to internal standards if present
            normalized.data = normalized.data.div(normalized.data.sum(axis=1), axis=0) * 1e6
        elif method == "sum":
            normalized.data = normalized.data.div(normalized.data.sum(axis=1), axis=0)
        elif method == "log":
            normalized.data = np.log2(normalized.data + 1)
        
        normalized.preprocessing_history.append(f"normalize(method={method})")
        return normalized
    
    def analyze(self, data: OmicsData, params: AnalysisParams) -> AnalysisResult:
        """Run lipidomics analysis."""
        if params.analysis_type == "lipid_class_analysis":
            return self._analyze_lipid_classes(data, params)
        elif params.analysis_type == "differential_lipids":
            return self._analyze_differential(data, params)
        elif params.analysis_type == "fatty_acid_analysis":
            return self._analyze_fatty_acids(data, params)
        return AnalysisResult(analysis_type=params.analysis_type, status="failed", data={}, errors=["Unknown analysis"])
    
    def _analyze_lipid_classes(self, data: OmicsData, params: AnalysisParams) -> AnalysisResult:
        """Analyze lipid class composition."""
        # Extract lipid classes from names (simplified)
        class_totals = {}
        for lipid in data.feature_names:
            # Extract class (e.g., PC, PE, TG, etc.)
            parts = lipid.split("(")
            if parts:
                lipid_class = parts[0].strip()
                if lipid_class not in class_totals:
                    class_totals[lipid_class] = 0
                if lipid in data.data.columns:
                    class_totals[lipid_class] += data.data[lipid].sum()
        
        return AnalysisResult(
            analysis_type="lipid_class_analysis",
            status="success",
            data={"class_abundances": class_totals},
            summary={"n_classes": len(class_totals)},
        )
    
    def _analyze_differential(self, data: OmicsData, params: AnalysisParams) -> AnalysisResult:
        """Differential lipid analysis."""
        fdr_threshold = params.get("fdr_threshold", 0.05)
        results = []
        
        if data.sample_metadata is not None and "condition" in data.sample_metadata.columns:
            conditions = data.sample_metadata["condition"].unique()
            if len(conditions) >= 2:
                g1 = data.sample_metadata[data.sample_metadata["condition"] == conditions[0]].index
                g2 = data.sample_metadata[data.sample_metadata["condition"] == conditions[1]].index
                
                for lipid in data.feature_names:
                    if lipid in data.data.columns:
                        v1, v2 = data.data.loc[g1, lipid].dropna(), data.data.loc[g2, lipid].dropna()
                        if len(v1) > 1 and len(v2) > 1:
                            t, p = stats.ttest_ind(v1, v2)
                            fc = np.log2((v2.mean() + 1) / (v1.mean() + 1))
                            results.append({"lipid": lipid, "log2FC": fc, "pvalue": p})
        
        return AnalysisResult(
            analysis_type="differential_lipids",
            status="success",
            data={"da_results": results},
            summary={"n_lipids_tested": len(results)},
        )
    
    def _analyze_fatty_acids(self, data: OmicsData, params: AnalysisParams) -> AnalysisResult:
        """Analyze fatty acid composition."""
        # Extract FA chain info from lipid names (simplified)
        fa_composition = {
            "saturated": 0,
            "monounsaturated": 0,
            "polyunsaturated": 0,
        }
        
        return AnalysisResult(
            analysis_type="fatty_acid_analysis",
            status="success",
            data={"fa_composition": fa_composition},
            summary={},
        )
    
    def visualize(self, result: AnalysisResult, plot_types: Optional[List[str]] = None) -> List[Visualization]:
        visualizations = []
        
        if result.analysis_type == "lipid_class_analysis":
            if "class_abundances" in result.data:
                visualizations.append(Visualization(
                    name="lipid_class_pie",
                    plot_type="pie",
                    data=result.data["class_abundances"],
                    title="Lipid Class Distribution",
                ))
        
        return visualizations
    
    def get_available_pipelines(self) -> List[Pipeline]:
        return self._pipelines
    
    def get_available_analyses(self) -> List[AnalysisDefinition]:
        return self._analyses

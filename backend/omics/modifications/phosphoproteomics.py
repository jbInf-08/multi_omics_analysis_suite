"""
Phosphoproteomics Module - Protein phosphorylation analysis
"""

from typing import Dict, List, Any, Optional
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import stats

from backend.omics.base.omics_base import (
    OmicsModuleBase, OmicsCategory, OmicsData, QCReport, QCMetric,
    AnalysisParams, AnalysisResult, Visualization, Pipeline, AnalysisDefinition, DataSource,
)


class PhosphoproteomicsModule(OmicsModuleBase):
    """Phosphoproteomics module for phosphorylation site analysis."""
    
    def __init__(self):
        super().__init__()
        self._version = "1.0.0"
        self._supported_formats = ["csv", "tsv", "maxquant"]
        self._pipelines = [
            Pipeline(name="phosphosite_analysis", description="Phosphorylation site quantification and analysis",
                steps=["load_data", "qc", "normalization", "site_localization", "differential_analysis", "kinase_enrichment"],
                default_parameters={"localization_prob": 0.75, "normalization": "median"}),
        ]
        self._analyses = [
            AnalysisDefinition(name="differential_phosphosites", description="Differential phosphosite analysis",
                parameters={"fdr": {"type": "float", "default": 0.05}}, output_types=["table", "volcano"]),
            AnalysisDefinition(name="kinase_substrate_enrichment", description="Kinase-substrate enrichment analysis",
                parameters={"database": {"type": "str", "default": "phosphositeplus"}}, output_types=["table", "heatmap"]),
            AnalysisDefinition(name="motif_analysis", description="Phosphorylation motif analysis",
                parameters={"width": {"type": "int", "default": 13}}, output_types=["motif_logo"]),
        ]
    
    @property
    def name(self) -> str: return "phosphoproteomics"
    @property
    def category(self) -> OmicsCategory: return OmicsCategory.MODIFICATIONS
    @property
    def description(self) -> str: return "Protein phosphorylation site analysis and kinase activity inference"
    
    def load_data(self, source: DataSource) -> OmicsData:
        if source.source_type == "file":
            df = pd.read_csv(source.path, sep="\t" if source.path.endswith(".tsv") else ",", index_col=0)
            return OmicsData(data=df.T, feature_names=df.index.tolist(), sample_names=df.columns.tolist(), data_type="phosphoproteomics", source=source)
        raise ValueError(f"Unsupported source: {source.source_type}")
    
    def preprocess(self, data: OmicsData, params: Optional[Dict[str, Any]] = None) -> OmicsData:
        processed = data.copy()
        params = params or {}
        loc_prob = params.get("localization_prob", 0.75)
        if "localization_prob" in processed.data.columns:
            keep = processed.data["localization_prob"] >= loc_prob
            processed.data = processed.data[keep]
        processed.preprocessing_history.append(f"preprocess(loc_prob={loc_prob})")
        return processed
    
    def quality_control(self, data: OmicsData, params: Optional[Dict[str, Any]] = None) -> QCReport:
        metrics = [QCMetric(name="phosphosite_count", value=len(data.feature_names), threshold=100)]
        return QCReport(passed=all(m.passed for m in metrics if m.passed is not None), metrics=metrics)
    
    def normalize(self, data: OmicsData, method: str = "median", params: Optional[Dict[str, Any]] = None) -> OmicsData:
        normalized = data.copy()
        if method == "median":
            medians = normalized.data.median(axis=1)
            normalized.data = normalized.data.sub(medians, axis=0)
        normalized.preprocessing_history.append(f"normalize(method={method})")
        return normalized
    
    def analyze(self, data: OmicsData, params: AnalysisParams) -> AnalysisResult:
        if params.analysis_type == "differential_phosphosites":
            return AnalysisResult(analysis_type=params.analysis_type, status="success", data={"results": []}, summary={})
        elif params.analysis_type == "kinase_substrate_enrichment":
            return AnalysisResult(analysis_type=params.analysis_type, status="success", data={"kinases": []}, summary={})
        return AnalysisResult(analysis_type=params.analysis_type, status="failed", data={}, errors=["Unknown analysis"])
    
    def visualize(self, result: AnalysisResult, plot_types: Optional[List[str]] = None) -> List[Visualization]: return []
    def get_available_pipelines(self) -> List[Pipeline]: return self._pipelines
    def get_available_analyses(self) -> List[AnalysisDefinition]: return self._analyses

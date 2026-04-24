"""
Synaptomics Module - Synaptic proteomics and connectivity
"""

from typing import Dict, List, Any, Optional
import pandas as pd
from backend.omics.base.omics_base import (
    OmicsModuleBase, OmicsCategory, OmicsData, QCReport, QCMetric,
    AnalysisParams, AnalysisResult, Visualization, Pipeline, AnalysisDefinition, DataSource,
)


class SynaptomicsModule(OmicsModuleBase):
    """Synaptomics module for synaptic protein analysis."""
    
    def __init__(self):
        super().__init__()
        self._version = "1.0.0"
        self._supported_formats = ["csv", "tsv"]
        self._pipelines = [
            Pipeline(name="synaptic_analysis", description="Synaptic proteome analysis",
                steps=["load_data", "qc", "compartment_assignment", "differential_analysis", "pathway_analysis"],
                default_parameters={"compartments": ["presynaptic", "postsynaptic"]}),
        ]
        self._analyses = [
            AnalysisDefinition(name="synaptic_composition", description="Synaptic protein composition",
                parameters={}, output_types=["table", "bar_chart"]),
            AnalysisDefinition(name="differential_synaptic", description="Differential synaptic proteins",
                parameters={"fdr": {"type": "float", "default": 0.05}}, output_types=["table"]),
        ]
    
    @property
    def name(self) -> str: return "synaptomics"
    @property
    def category(self) -> OmicsCategory: return OmicsCategory.INTERACTIONS
    @property
    def description(self) -> str: return "Synaptic proteomics and connectivity analysis"
    
    def load_data(self, source: DataSource) -> OmicsData:
        if source.source_type == "file":
            df = pd.read_csv(source.path, sep="\t" if source.path.endswith(".tsv") else ",", index_col=0)
            return OmicsData(data=df.T, feature_names=df.index.tolist(), sample_names=df.columns.tolist(), data_type="synaptomics", source=source)
        raise ValueError(f"Unsupported source: {source.source_type}")
    
    def preprocess(self, data: OmicsData, params: Optional[Dict[str, Any]] = None) -> OmicsData:
        processed = data.copy()
        processed.preprocessing_history.append("preprocess()")
        return processed
    
    def quality_control(self, data: OmicsData, params: Optional[Dict[str, Any]] = None) -> QCReport:
        metrics = [QCMetric(name="protein_count", value=len(data.feature_names), threshold=100)]
        return QCReport(passed=all(m.passed for m in metrics if m.passed is not None), metrics=metrics)
    
    def normalize(self, data: OmicsData, method: str = "median", params: Optional[Dict[str, Any]] = None) -> OmicsData:
        normalized = data.copy()
        normalized.preprocessing_history.append(f"normalize(method={method})")
        return normalized
    
    def analyze(self, data: OmicsData, params: AnalysisParams) -> AnalysisResult:
        return AnalysisResult(analysis_type=params.analysis_type, status="success", data={}, summary={})
    
    def visualize(self, result: AnalysisResult, plot_types: Optional[List[str]] = None) -> List[Visualization]: return []
    def get_available_pipelines(self) -> List[Pipeline]: return self._pipelines
    def get_available_analyses(self) -> List[AnalysisDefinition]: return self._analyses

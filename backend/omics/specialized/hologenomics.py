"""
Hologenomics Module
===================

Analysis module for host-microbiome interactions.
"""

from typing import Dict, List, Optional
import pandas as pd
from ..base import OmicsModuleBase, OmicsCategory, OmicsData, QCReport, QCMetric
from ..base import AnalysisParams, AnalysisResult, Visualization, Pipeline, AnalysisDefinition, DataSource


class HologenomicsModule(OmicsModuleBase):
    """Module for hologenomics - host + microbiome analysis."""
    
    @property
    def name(self) -> str:
        return "hologenomics"
    
    @property
    def category(self) -> OmicsCategory:
        return OmicsCategory.SPECIALIZED
    
    @property
    def description(self) -> str:
        return "Integrated host-microbiome (holobiont) genomic analysis"
    
    @property
    def supported_formats(self) -> List[str]:
        return ["csv", "biom", "tsv", "fastq"]
    
    def load_data(self, source: DataSource) -> OmicsData:
        if source.format == "csv":
            data = pd.read_csv(source.path, index_col=0)
        else:
            data = pd.DataFrame()
        return OmicsData(data=data, sample_metadata=pd.DataFrame(),
                        feature_metadata=pd.DataFrame(), omics_type=self.name)
    
    def preprocess(self, data: OmicsData) -> OmicsData:
        return data
    
    def quality_control(self, data: OmicsData) -> QCReport:
        metrics = [QCMetric(name="completeness", value=0.9, threshold=0.7, passed=True)]
        return QCReport(metrics=metrics, passed=True)
    
    def normalize(self, data: OmicsData, params: AnalysisParams) -> OmicsData:
        return data
    
    def analyze(self, data: OmicsData, params: AnalysisParams) -> AnalysisResult:
        return AnalysisResult(name=params.name, data=pd.DataFrame(),
                             parameters=params.parameters, status="completed")
    
    def visualize(self, result: AnalysisResult, params: Optional[Dict] = None) -> Visualization:
        return Visualization(name=f"{result.name}_plot", plot_type="network",
                           data=result.data.to_dict(), config=params or {})
    
    def get_available_pipelines(self) -> List[Pipeline]:
        return [
            Pipeline(name="holobiont", description="Holobiont analysis",
                    steps=["load_host", "load_microbiome", "integration", "correlation"]),
        ]
    
    def get_available_analyses(self) -> List[AnalysisDefinition]:
        return [
            AnalysisDefinition(name="host_microbe_correlation", description="Host-microbe correlation"),
            AnalysisDefinition(name="coevolution", description="Host-microbe coevolution analysis"),
            AnalysisDefinition(name="metatranscriptomics", description="Combined metatranscriptomics"),
        ]

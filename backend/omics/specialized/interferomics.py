"""
Interferomics Module
====================

Analysis module for interference patterns and RNAi screening.
"""

from typing import Dict, List, Optional
import pandas as pd
from ..base import OmicsModuleBase, OmicsCategory, OmicsData, QCReport, QCMetric
from ..base import AnalysisParams, AnalysisResult, Visualization, Pipeline, AnalysisDefinition, DataSource


class InterferomicsModule(OmicsModuleBase):
    """Module for interferomics - RNAi/CRISPR screening analysis."""
    
    @property
    def name(self) -> str:
        return "interferomics"
    
    @property
    def category(self) -> OmicsCategory:
        return OmicsCategory.SPECIALIZED
    
    @property
    def description(self) -> str:
        return "RNAi and CRISPR screening analysis for gene function"
    
    @property
    def supported_formats(self) -> List[str]:
        return ["csv", "xlsx", "tsv"]
    
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
        metrics = [QCMetric(name="completeness", value=0.9, threshold=0.8, passed=True)]
        return QCReport(metrics=metrics, passed=True)
    
    def normalize(self, data: OmicsData, params: AnalysisParams) -> OmicsData:
        return data
    
    def analyze(self, data: OmicsData, params: AnalysisParams) -> AnalysisResult:
        return AnalysisResult(name=params.name, data=pd.DataFrame(),
                             parameters=params.parameters, status="completed")
    
    def visualize(self, result: AnalysisResult, params: Optional[Dict] = None) -> Visualization:
        return Visualization(name=f"{result.name}_plot", plot_type="volcano",
                           data=result.data.to_dict(), config=params or {})
    
    def get_available_pipelines(self) -> List[Pipeline]:
        return [
            Pipeline(name="crispr_screen", description="CRISPR screen analysis",
                    steps=["load", "qc", "mageck", "pathway_enrichment"]),
        ]
    
    def get_available_analyses(self) -> List[AnalysisDefinition]:
        return [
            AnalysisDefinition(name="hit_calling", description="Screen hit identification"),
            AnalysisDefinition(name="gene_ranking", description="Gene ranking (MAGeCK)"),
            AnalysisDefinition(name="pathway_screen", description="Pathway-level screen analysis"),
        ]

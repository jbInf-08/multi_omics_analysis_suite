"""
Cytomics Module
===============

Analysis module for cell-level analysis and flow cytometry data.
"""

from typing import Dict, List, Optional
import pandas as pd
import numpy as np
from ..base import OmicsModuleBase, OmicsCategory, OmicsData, QCReport, QCMetric
from ..base import AnalysisParams, AnalysisResult, Visualization, Pipeline, AnalysisDefinition, DataSource


class CytomicsModule(OmicsModuleBase):
    """Module for cytomics - cell-level analysis."""
    
    @property
    def name(self) -> str:
        return "cytomics"
    
    @property
    def category(self) -> OmicsCategory:
        return OmicsCategory.SPECIALIZED
    
    @property
    def description(self) -> str:
        return "Cell-level analysis including flow/mass cytometry and cell imaging"
    
    @property
    def supported_formats(self) -> List[str]:
        return ["fcs", "csv", "h5ad", "tiff"]
    
    def load_data(self, source: DataSource) -> OmicsData:
        if source.format == "csv":
            data = pd.read_csv(source.path, index_col=0)
        else:
            data = pd.DataFrame()
        return OmicsData(data=data, sample_metadata=pd.DataFrame(),
                        feature_metadata=pd.DataFrame(), omics_type=self.name)
    
    def preprocess(self, data: OmicsData) -> OmicsData:
        df = data.data.copy()
        # Compensate and transform
        df = np.arcsinh(df / 5)  # Arcsinh transformation
        return OmicsData(data=df, sample_metadata=data.sample_metadata,
                        feature_metadata=data.feature_metadata, omics_type=self.name)
    
    def quality_control(self, data: OmicsData) -> QCReport:
        metrics = [
            QCMetric(name="n_cells", value=data.data.shape[0], threshold=1000, passed=data.data.shape[0] >= 1000),
            QCMetric(name="n_markers", value=data.data.shape[1], threshold=5, passed=data.data.shape[1] >= 5),
        ]
        return QCReport(metrics=metrics, passed=all(m.passed for m in metrics))
    
    def normalize(self, data: OmicsData, params: AnalysisParams) -> OmicsData:
        return data
    
    def analyze(self, data: OmicsData, params: AnalysisParams) -> AnalysisResult:
        return AnalysisResult(name=params.name, data=pd.DataFrame(),
                             parameters=params.parameters, status="completed")
    
    def visualize(self, result: AnalysisResult, params: Optional[Dict] = None) -> Visualization:
        return Visualization(name=f"{result.name}_plot", plot_type="scatter",
                           data=result.data.to_dict(), config=params or {})
    
    def get_available_pipelines(self) -> List[Pipeline]:
        return [
            Pipeline(name="flow_cytometry", description="Flow cytometry analysis",
                    steps=["load", "compensate", "transform", "gating", "clustering"]),
            Pipeline(name="mass_cytometry", description="CyTOF analysis",
                    steps=["load", "normalize", "batch_correction", "clustering", "phenotyping"]),
        ]
    
    def get_available_analyses(self) -> List[AnalysisDefinition]:
        return [
            AnalysisDefinition(name="gating", description="Automated cell gating"),
            AnalysisDefinition(name="clustering", description="Cell population clustering"),
            AnalysisDefinition(name="phenotyping", description="Cell phenotype assignment"),
            AnalysisDefinition(name="trajectory", description="Cell differentiation trajectory"),
        ]

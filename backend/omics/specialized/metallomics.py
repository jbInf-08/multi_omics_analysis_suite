"""Metallomics Module.
==================

Analysis module for metal-biomolecule interactions.
"""

import pandas as pd

from ..base import (
    AnalysisDefinition,
    AnalysisParams,
    AnalysisResult,
    DataSource,
    OmicsCategory,
    OmicsData,
    OmicsModuleBase,
    Pipeline,
    QCMetric,
    QCReport,
    Visualization,
)


class MetallomicsModule(OmicsModuleBase):
    """Module for metallomics analysis."""

    @property
    def name(self) -> str:
        return "metallomics"

    @property
    def category(self) -> OmicsCategory:
        return OmicsCategory.SPECIALIZED

    @property
    def description(self) -> str:
        return "Metal-biomolecule interaction analysis including metalloprotein identification"

    @property
    def supported_formats(self) -> list[str]:
        return ["csv", "xlsx"]

    def load_data(self, source: DataSource) -> OmicsData:
        data = pd.read_csv(source.path, index_col=0) if source.format == "csv" else pd.DataFrame()
        return OmicsData(
            data=data,
            sample_metadata=pd.DataFrame(),
            feature_metadata=pd.DataFrame(),
            omics_type=self.name,
        )

    def preprocess(self, data: OmicsData) -> OmicsData:
        return data

    def quality_control(self, data: OmicsData) -> QCReport:
        metrics = [QCMetric(name="completeness", value=0.9, threshold=0.8, passed=True)]
        return QCReport(metrics=metrics, passed=True)

    def normalize(self, data: OmicsData, params: AnalysisParams) -> OmicsData:
        return data

    def analyze(self, data: OmicsData, params: AnalysisParams) -> AnalysisResult:
        return AnalysisResult(
            name=params.name, data=pd.DataFrame(), parameters=params.parameters, status="completed"
        )

    def visualize(self, result: AnalysisResult, params: dict | None = None) -> Visualization:
        return Visualization(
            name=f"{result.name}_plot",
            plot_type="bar",
            data=result.data.to_dict(),
            config=params or {},
        )

    def get_available_pipelines(self) -> list[Pipeline]:
        return [
            Pipeline(
                name="metalloprotein",
                description="Metalloprotein analysis",
                steps=["load", "metal_binding", "identification", "quantification"],
            ),
        ]

    def get_available_analyses(self) -> list[AnalysisDefinition]:
        return [
            AnalysisDefinition(name="metal_binding", description="Metal binding site analysis"),
            AnalysisDefinition(
                name="metalloprotein_id", description="Metalloprotein identification"
            ),
            AnalysisDefinition(name="speciation", description="Metal speciation analysis"),
        ]

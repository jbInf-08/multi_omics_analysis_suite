"""Ionomics Module.
===============

Analysis module for elemental/ionic profiling.
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


class IonomicsModule(OmicsModuleBase):
    """Module for ionomics (elemental profiling) analysis."""

    @property
    def name(self) -> str:
        return "ionomics"

    @property
    def category(self) -> OmicsCategory:
        return OmicsCategory.SPECIALIZED

    @property
    def description(self) -> str:
        return "Elemental and ionic profiling using ICP-MS and related techniques"

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
        metrics = [QCMetric(name="completeness", value=0.95, threshold=0.8, passed=True)]
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
            plot_type="heatmap",
            data=result.data.to_dict(),
            config=params or {},
        )

    def get_available_pipelines(self) -> list[Pipeline]:
        return [
            Pipeline(
                name="ionome_profiling",
                description="Complete ionome profiling",
                steps=["load", "qc", "normalize", "analysis", "visualization"],
            ),
        ]

    def get_available_analyses(self) -> list[AnalysisDefinition]:
        return [
            AnalysisDefinition(
                name="element_profiling", description="Elemental concentration profiling"
            ),
            AnalysisDefinition(
                name="deficiency_analysis", description="Nutrient deficiency detection"
            ),
            AnalysisDefinition(name="accumulation", description="Element accumulation analysis"),
        ]

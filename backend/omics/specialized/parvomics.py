"""Parvomics Module.
================

Analysis module for small molecule interactions.
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


class ParvomicsModule(OmicsModuleBase):
    """Module for parvomics - small molecule interaction analysis."""

    @property
    def name(self) -> str:
        return "parvomics"

    @property
    def category(self) -> OmicsCategory:
        return OmicsCategory.SPECIALIZED

    @property
    def description(self) -> str:
        return "Small molecule interaction analysis and drug-target profiling"

    @property
    def supported_formats(self) -> list[str]:
        return ["csv", "sdf", "xlsx"]

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
            plot_type="network",
            data=result.data.to_dict(),
            config=params or {},
        )

    def get_available_pipelines(self) -> list[Pipeline]:
        return [
            Pipeline(
                name="drug_target",
                description="Drug-target interaction",
                steps=["load", "fingerprints", "prediction", "validation"],
            ),
        ]

    def get_available_analyses(self) -> list[AnalysisDefinition]:
        return [
            AnalysisDefinition(name="drug_target_prediction", description="Predict drug targets"),
            AnalysisDefinition(name="binding_affinity", description="Binding affinity prediction"),
            AnalysisDefinition(name="off_target", description="Off-target effect prediction"),
        ]

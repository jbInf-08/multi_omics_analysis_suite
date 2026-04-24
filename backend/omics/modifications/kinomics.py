"""Kinomics Module - Kinase activity profiling."""

from typing import Any

import pandas as pd

from backend.omics.base.omics_base import (
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


class KinomicsModule(OmicsModuleBase):
    """Kinomics module for kinase activity profiling."""

    def __init__(self):
        super().__init__()
        self._version = "1.0.0"
        self._supported_formats = ["csv", "tsv"]
        self._pipelines = [
            Pipeline(
                name="kinase_profiling",
                description="Kinase activity profiling pipeline",
                steps=[
                    "load_data",
                    "qc",
                    "substrate_mapping",
                    "activity_inference",
                    "pathway_analysis",
                ],
                default_parameters={"database": "phosphositeplus"},
            ),
        ]
        self._analyses = [
            AnalysisDefinition(
                name="kinase_activity",
                description="Kinase activity inference",
                parameters={"method": {"type": "str", "default": "ksea"}},
                output_types=["table", "heatmap"],
            ),
            AnalysisDefinition(
                name="kinase_network",
                description="Kinase signaling network analysis",
                parameters={},
                output_types=["network"],
            ),
        ]

    @property
    def name(self) -> str:
        return "kinomics"

    @property
    def category(self) -> OmicsCategory:
        return OmicsCategory.MODIFICATIONS

    @property
    def description(self) -> str:
        return "Kinase activity profiling and signaling network analysis"

    def load_data(self, source: DataSource) -> OmicsData:
        if source.source_type == "file":
            df = pd.read_csv(
                source.path, sep="\t" if source.path.endswith(".tsv") else ",", index_col=0
            )
            return OmicsData(
                data=df.T,
                feature_names=df.index.tolist(),
                sample_names=df.columns.tolist(),
                data_type="kinomics",
                source=source,
            )
        raise ValueError(f"Unsupported source: {source.source_type}")

    def preprocess(self, data: OmicsData, params: dict[str, Any] | None = None) -> OmicsData:
        processed = data.copy()
        processed.preprocessing_history.append("preprocess()")
        return processed

    def quality_control(self, data: OmicsData, params: dict[str, Any] | None = None) -> QCReport:
        metrics = [QCMetric(name="feature_count", value=len(data.feature_names), threshold=10)]
        return QCReport(
            passed=all(m.passed for m in metrics if m.passed is not None), metrics=metrics
        )

    def normalize(
        self, data: OmicsData, method: str = "zscore", params: dict[str, Any] | None = None
    ) -> OmicsData:
        normalized = data.copy()
        normalized.preprocessing_history.append(f"normalize(method={method})")
        return normalized

    def analyze(self, data: OmicsData, params: AnalysisParams) -> AnalysisResult:
        return AnalysisResult(
            analysis_type=params.analysis_type, status="success", data={}, summary={}
        )

    def visualize(
        self, result: AnalysisResult, plot_types: list[str] | None = None
    ) -> list[Visualization]:
        return []

    def get_available_pipelines(self) -> list[Pipeline]:
        return self._pipelines

    def get_available_analyses(self) -> list[AnalysisDefinition]:
        return self._analyses

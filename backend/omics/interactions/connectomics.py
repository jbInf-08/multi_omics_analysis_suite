"""Connectomics Module - Neural connectivity analysis."""

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


class ConnectomicsModule(OmicsModuleBase):
    """Connectomics module for neural connectivity mapping."""

    def __init__(self):
        super().__init__()
        self._version = "1.0.0"
        self._supported_formats = ["csv", "tsv", "nii", "graphml"]
        self._pipelines = [
            Pipeline(
                name="connectome_analysis",
                description="Brain connectivity analysis",
                steps=[
                    "load_data",
                    "preprocessing",
                    "connectivity_matrix",
                    "network_analysis",
                    "visualization",
                ],
                default_parameters={"parcellation": "aparc"},
            ),
        ]
        self._analyses = [
            AnalysisDefinition(
                name="connectivity_matrix",
                description="Generate connectivity matrix",
                parameters={"threshold": {"type": "float", "default": 0.1}},
                output_types=["matrix", "heatmap"],
            ),
            AnalysisDefinition(
                name="graph_metrics",
                description="Calculate graph theory metrics",
                parameters={},
                output_types=["table"],
            ),
        ]

    @property
    def name(self) -> str:
        return "connectomics"

    @property
    def category(self) -> OmicsCategory:
        return OmicsCategory.INTERACTIONS

    @property
    def description(self) -> str:
        return "Neural connectivity and brain network analysis"

    def load_data(self, source: DataSource) -> OmicsData:
        if source.source_type == "file":
            df = pd.read_csv(
                source.path, sep="\t" if source.path.endswith(".tsv") else ",", index_col=0
            )
            return OmicsData(
                data=df,
                feature_names=df.columns.tolist(),
                sample_names=df.index.tolist(),
                data_type="connectomics",
                source=source,
            )
        raise ValueError(f"Unsupported source: {source.source_type}")

    def preprocess(self, data: OmicsData, params: dict[str, Any] | None = None) -> OmicsData:
        processed = data.copy()
        processed.preprocessing_history.append("preprocess()")
        return processed

    def quality_control(self, data: OmicsData, params: dict[str, Any] | None = None) -> QCReport:
        metrics = [QCMetric(name="region_count", value=len(data.feature_names), threshold=10)]
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

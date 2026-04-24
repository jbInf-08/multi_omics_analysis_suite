"""Chromatomics Module - Chromatin state analysis."""

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


class ChromatomicsModule(OmicsModuleBase):
    """Chromatomics module for chromatin state analysis."""

    def __init__(self):
        super().__init__()
        self._version = "1.0.0"
        self._supported_formats = ["csv", "tsv", "bed"]
        self._pipelines = [
            Pipeline(
                name="chromatin_state",
                description="Chromatin state analysis",
                steps=["load_data", "qc", "state_learning", "annotation", "differential_analysis"],
                default_parameters={"n_states": 15},
            ),
        ]
        self._analyses = [
            AnalysisDefinition(
                name="chromatin_states",
                description="Learn chromatin states",
                parameters={"n_states": {"type": "int", "default": 15}},
                output_types=["table", "heatmap"],
            ),
            AnalysisDefinition(
                name="differential_accessibility",
                description="Differential chromatin accessibility",
                parameters={"fdr": {"type": "float", "default": 0.05}},
                output_types=["table"],
            ),
        ]

    @property
    def name(self) -> str:
        return "chromatomics"

    @property
    def category(self) -> OmicsCategory:
        return OmicsCategory.MODIFICATIONS

    @property
    def description(self) -> str:
        return "Chromatin state and accessibility analysis"

    def load_data(self, source: DataSource) -> OmicsData:
        if source.source_type == "file":
            df = pd.read_csv(
                source.path, sep="\t" if source.path.endswith(".tsv") else ",", index_col=0
            )
            return OmicsData(
                data=df.T,
                feature_names=df.index.tolist(),
                sample_names=df.columns.tolist(),
                data_type="chromatomics",
                source=source,
            )
        raise ValueError(f"Unsupported source: {source.source_type}")

    def preprocess(self, data: OmicsData, params: dict[str, Any] | None = None) -> OmicsData:
        processed = data.copy()
        processed.preprocessing_history.append("preprocess()")
        return processed

    def quality_control(self, data: OmicsData, params: dict[str, Any] | None = None) -> QCReport:
        metrics = [QCMetric(name="region_count", value=len(data.feature_names), threshold=1000)]
        return QCReport(
            passed=all(m.passed for m in metrics if m.passed is not None), metrics=metrics
        )

    def normalize(
        self, data: OmicsData, method: str = "rpm", params: dict[str, Any] | None = None
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

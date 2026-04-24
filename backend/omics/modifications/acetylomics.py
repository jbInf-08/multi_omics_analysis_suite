"""Acetylomics Module - Protein acetylation analysis."""

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


class AcetylomicsModule(OmicsModuleBase):
    """Acetylomics module for lysine acetylation analysis."""

    def __init__(self):
        super().__init__()
        self._version = "1.0.0"
        self._supported_formats = ["csv", "tsv"]
        self._pipelines = [
            Pipeline(
                name="acetylation_analysis",
                description="Protein acetylation site analysis",
                steps=[
                    "load_data",
                    "qc",
                    "site_localization",
                    "quantification",
                    "differential_analysis",
                ],
                default_parameters={"modification": "K-Ac"},
            ),
        ]
        self._analyses = [
            AnalysisDefinition(
                name="differential_acetylation",
                description="Differential acetylation analysis",
                parameters={"fdr": {"type": "float", "default": 0.05}},
                output_types=["table", "volcano"],
            ),
            AnalysisDefinition(
                name="histone_acetylation",
                description="Histone-specific acetylation analysis",
                parameters={},
                output_types=["table", "heatmap"],
            ),
        ]

    @property
    def name(self) -> str:
        return "acetylomics"

    @property
    def category(self) -> OmicsCategory:
        return OmicsCategory.MODIFICATIONS

    @property
    def description(self) -> str:
        return "Protein lysine acetylation and histone modification analysis"

    def load_data(self, source: DataSource) -> OmicsData:
        if source.source_type == "file":
            df = pd.read_csv(
                source.path, sep="\t" if source.path.endswith(".tsv") else ",", index_col=0
            )
            return OmicsData(
                data=df.T,
                feature_names=df.index.tolist(),
                sample_names=df.columns.tolist(),
                data_type="acetylomics",
                source=source,
            )
        raise ValueError(f"Unsupported source: {source.source_type}")

    def preprocess(self, data: OmicsData, params: dict[str, Any] | None = None) -> OmicsData:
        processed = data.copy()
        processed.preprocessing_history.append("preprocess()")
        return processed

    def quality_control(self, data: OmicsData, params: dict[str, Any] | None = None) -> QCReport:
        metrics = [QCMetric(name="acetylsite_count", value=len(data.feature_names), threshold=50)]
        return QCReport(
            passed=all(m.passed for m in metrics if m.passed is not None), metrics=metrics
        )

    def normalize(
        self, data: OmicsData, method: str = "median", params: dict[str, Any] | None = None
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

"""Methylomics Module - Protein methylation analysis (distinct from DNA methylation in epigenomics)."""

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


class MethylomicsModule(OmicsModuleBase):
    """Methylomics module for protein methylation analysis."""

    def __init__(self):
        super().__init__()
        self._version = "1.0.0"
        self._supported_formats = ["csv", "tsv"]
        self._pipelines = [
            Pipeline(
                name="methylation_analysis",
                description="Protein methylation site analysis",
                steps=[
                    "load_data",
                    "qc",
                    "site_identification",
                    "quantification",
                    "differential_analysis",
                ],
                default_parameters={"modifications": ["K-Me", "R-Me"]},
            ),
        ]
        self._analyses = [
            AnalysisDefinition(
                name="differential_methylation",
                description="Differential protein methylation",
                parameters={"fdr": {"type": "float", "default": 0.05}},
                output_types=["table"],
            ),
            AnalysisDefinition(
                name="histone_methylation",
                description="Histone methylation marks analysis",
                parameters={},
                output_types=["table", "heatmap"],
            ),
        ]

    @property
    def name(self) -> str:
        return "methylomics"

    @property
    def category(self) -> OmicsCategory:
        return OmicsCategory.MODIFICATIONS

    @property
    def description(self) -> str:
        return "Protein arginine and lysine methylation analysis"

    def load_data(self, source: DataSource) -> OmicsData:
        if source.source_type == "file":
            df = pd.read_csv(
                source.path, sep="\t" if source.path.endswith(".tsv") else ",", index_col=0
            )
            return OmicsData(
                data=df.T,
                feature_names=df.index.tolist(),
                sample_names=df.columns.tolist(),
                data_type="methylomics",
                source=source,
            )
        raise ValueError(f"Unsupported source: {source.source_type}")

    def preprocess(self, data: OmicsData, params: dict[str, Any] | None = None) -> OmicsData:
        processed = data.copy()
        processed.preprocessing_history.append("preprocess()")
        return processed

    def quality_control(self, data: OmicsData, params: dict[str, Any] | None = None) -> QCReport:
        metrics = [QCMetric(name="methylsite_count", value=len(data.feature_names), threshold=20)]
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

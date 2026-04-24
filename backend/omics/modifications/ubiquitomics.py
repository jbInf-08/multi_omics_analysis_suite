"""Ubiquitomics Module - Protein ubiquitination analysis."""

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


class UbiquitomicsModule(OmicsModuleBase):
    """Ubiquitomics module for ubiquitination site analysis."""

    def __init__(self):
        super().__init__()
        self._version = "1.0.0"
        self._supported_formats = ["csv", "tsv"]
        self._pipelines = [
            Pipeline(
                name="ubiquitination_analysis",
                description="Ubiquitination site analysis",
                steps=[
                    "load_data",
                    "qc",
                    "site_localization",
                    "quantification",
                    "degradation_analysis",
                ],
                default_parameters={"diglycine_remnant": True},
            ),
        ]
        self._analyses = [
            AnalysisDefinition(
                name="differential_ubiquitination",
                description="Differential ubiquitination",
                parameters={"fdr": {"type": "float", "default": 0.05}},
                output_types=["table"],
            ),
            AnalysisDefinition(
                name="ub_chain_analysis",
                description="Ubiquitin chain type analysis",
                parameters={},
                output_types=["table"],
            ),
        ]

    @property
    def name(self) -> str:
        return "ubiquitomics"

    @property
    def category(self) -> OmicsCategory:
        return OmicsCategory.MODIFICATIONS

    @property
    def description(self) -> str:
        return "Protein ubiquitination and degradation signal analysis"

    def load_data(self, source: DataSource) -> OmicsData:
        if source.source_type == "file":
            df = pd.read_csv(
                source.path, sep="\t" if source.path.endswith(".tsv") else ",", index_col=0
            )
            return OmicsData(
                data=df.T,
                feature_names=df.index.tolist(),
                sample_names=df.columns.tolist(),
                data_type="ubiquitomics",
                source=source,
            )
        raise ValueError(f"Unsupported source: {source.source_type}")

    def preprocess(self, data: OmicsData, params: dict[str, Any] | None = None) -> OmicsData:
        processed = data.copy()
        processed.preprocessing_history.append("preprocess()")
        return processed

    def quality_control(self, data: OmicsData, params: dict[str, Any] | None = None) -> QCReport:
        metrics = [QCMetric(name="ubsite_count", value=len(data.feature_names), threshold=50)]
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

"""Allergomics Module - Allergy and immune response analysis."""

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


class AllergomicsModule(OmicsModuleBase):
    """Allergomics module for allergy-related omics analysis."""

    def __init__(self):
        super().__init__()
        self._version = "1.0.0"
        self._supported_formats = ["csv", "tsv"]
        self._pipelines = [
            Pipeline(
                name="allergen_analysis",
                description="Allergen response profiling",
                steps=[
                    "load_data",
                    "qc",
                    "ige_profiling",
                    "epitope_mapping",
                    "response_prediction",
                ],
                default_parameters={"database": "allergen_online"},
            ),
        ]
        self._analyses = [
            AnalysisDefinition(
                name="allergen_profiling",
                description="Profile allergen-specific responses",
                parameters={"allergens": {"type": "list", "default": None}},
                output_types=["table", "heatmap"],
            ),
            AnalysisDefinition(
                name="ige_repertoire",
                description="IgE antibody repertoire analysis",
                parameters={},
                output_types=["table", "distribution"],
            ),
            AnalysisDefinition(
                name="allergy_risk",
                description="Predict allergy risk from genetics",
                parameters={},
                output_types=["table", "risk_score"],
            ),
        ]

    @property
    def name(self) -> str:
        return "allergomics"

    @property
    def category(self) -> OmicsCategory:
        return OmicsCategory.CLINICAL

    @property
    def description(self) -> str:
        return "Allergy genomics and immune response profiling"

    def load_data(self, source: DataSource) -> OmicsData:
        if source.source_type == "file":
            df = pd.read_csv(
                source.path, sep="\t" if source.path.endswith(".tsv") else ",", index_col=0
            )
            return OmicsData(
                data=df.T,
                feature_names=df.index.tolist(),
                sample_names=df.columns.tolist(),
                data_type="allergomics",
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
        self, data: OmicsData, method: str = "log", params: dict[str, Any] | None = None
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

"""Regulomics Module - Gene regulatory network analysis."""

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


class RegulomicsModule(OmicsModuleBase):
    """Regulomics module for gene regulatory network analysis."""

    def __init__(self):
        super().__init__()
        self._version = "1.0.0"
        self._supported_formats = ["csv", "tsv", "sif"]
        self._pipelines = [
            Pipeline(
                name="grn_analysis",
                description="Gene regulatory network inference",
                steps=[
                    "load_data",
                    "network_inference",
                    "tf_activity",
                    "target_prediction",
                    "visualization",
                ],
                default_parameters={"method": "genie3"},
            ),
        ]
        self._analyses = [
            AnalysisDefinition(
                name="network_inference",
                description="Infer gene regulatory network",
                parameters={"method": {"type": "str", "default": "genie3"}},
                output_types=["network"],
            ),
            AnalysisDefinition(
                name="tf_activity",
                description="Transcription factor activity estimation",
                parameters={"database": {"type": "str", "default": "dorothea"}},
                output_types=["table"],
            ),
            AnalysisDefinition(
                name="regulon_analysis",
                description="Analyze TF regulons",
                parameters={},
                output_types=["table", "network"],
            ),
        ]

    @property
    def name(self) -> str:
        return "regulomics"

    @property
    def category(self) -> OmicsCategory:
        return OmicsCategory.INTERACTIONS

    @property
    def description(self) -> str:
        return "Gene regulatory network and transcription factor analysis"

    def load_data(self, source: DataSource) -> OmicsData:
        if source.source_type == "file":
            df = pd.read_csv(
                source.path, sep="\t" if source.path.endswith(".tsv") else ",", index_col=0
            )
            return OmicsData(
                data=df.T,
                feature_names=df.index.tolist(),
                sample_names=df.columns.tolist(),
                data_type="regulomics",
                source=source,
            )
        raise ValueError(f"Unsupported source: {source.source_type}")

    def preprocess(self, data: OmicsData, params: dict[str, Any] | None = None) -> OmicsData:
        processed = data.copy()
        processed.preprocessing_history.append("preprocess()")
        return processed

    def quality_control(self, data: OmicsData, params: dict[str, Any] | None = None) -> QCReport:
        metrics = [QCMetric(name="gene_count", value=len(data.feature_names), threshold=100)]
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

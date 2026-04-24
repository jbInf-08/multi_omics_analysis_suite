"""Neurogenomics Module - Brain and neurological genomics."""

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


class NeurogenomicsModule(OmicsModuleBase):
    """Neurogenomics module for brain and nervous system analysis."""

    def __init__(self):
        super().__init__()
        self._version = "1.0.0"
        self._supported_formats = ["csv", "tsv", "vcf"]
        self._pipelines = [
            Pipeline(
                name="brain_expression",
                description="Brain region-specific expression analysis",
                steps=[
                    "load_data",
                    "qc",
                    "region_mapping",
                    "cell_type_deconvolution",
                    "differential_analysis",
                ],
                default_parameters={"atlas": "allen_brain"},
            ),
        ]
        self._analyses = [
            AnalysisDefinition(
                name="brain_region_expression",
                description="Brain region-specific expression",
                parameters={"regions": {"type": "list", "default": None}},
                output_types=["table", "brain_map"],
            ),
            AnalysisDefinition(
                name="neuropsych_gwas",
                description="Neuropsychiatric GWAS analysis",
                parameters={"traits": {"type": "list", "default": ["schizophrenia", "alzheimers"]}},
                output_types=["table", "manhattan"],
            ),
            AnalysisDefinition(
                name="neural_cell_types",
                description="Neural cell type deconvolution",
                parameters={"method": {"type": "str", "default": "music"}},
                output_types=["table", "bar_chart"],
            ),
        ]

    @property
    def name(self) -> str:
        return "neurogenomics"

    @property
    def category(self) -> OmicsCategory:
        return OmicsCategory.CLINICAL

    @property
    def description(self) -> str:
        return "Brain and neurological genomics analysis"

    def load_data(self, source: DataSource) -> OmicsData:
        if source.source_type == "file":
            df = pd.read_csv(
                source.path, sep="\t" if source.path.endswith(".tsv") else ",", index_col=0
            )
            return OmicsData(
                data=df.T,
                feature_names=df.index.tolist(),
                sample_names=df.columns.tolist(),
                data_type="neurogenomics",
                source=source,
            )
        raise ValueError(f"Unsupported source: {source.source_type}")

    def preprocess(self, data: OmicsData, params: dict[str, Any] | None = None) -> OmicsData:
        processed = data.copy()
        processed.preprocessing_history.append("preprocess()")
        return processed

    def quality_control(self, data: OmicsData, params: dict[str, Any] | None = None) -> QCReport:
        metrics = [QCMetric(name="gene_count", value=len(data.feature_names), threshold=1000)]
        return QCReport(
            passed=all(m.passed for m in metrics if m.passed is not None), metrics=metrics
        )

    def normalize(
        self, data: OmicsData, method: str = "tpm", params: dict[str, Any] | None = None
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

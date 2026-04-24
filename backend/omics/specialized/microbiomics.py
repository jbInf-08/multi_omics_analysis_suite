"""Microbiomics Module.
===================

Analysis module for microbiome functional analysis.
"""

import numpy as np
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


class MicrobiomicsModule(OmicsModuleBase):
    """Module for microbiome functional and ecological analysis."""

    @property
    def name(self) -> str:
        return "microbiomics"

    @property
    def category(self) -> OmicsCategory:
        return OmicsCategory.SPECIALIZED

    @property
    def description(self) -> str:
        return "Microbiome functional analysis including metabolic reconstruction and host-microbe interactions"

    @property
    def supported_formats(self) -> list[str]:
        return ["csv", "biom", "qza", "tsv"]

    def load_data(self, source: DataSource) -> OmicsData:
        if source.format in ["csv", "tsv"]:
            sep = "\t" if source.format == "tsv" else ","
            data = pd.read_csv(source.path, index_col=0, sep=sep)
        else:
            data = pd.DataFrame()
        return OmicsData(
            data=data,
            sample_metadata=pd.DataFrame(),
            feature_metadata=pd.DataFrame(),
            omics_type=self.name,
        )

    def preprocess(self, data: OmicsData) -> OmicsData:
        df = data.data.copy()
        # Filter low abundance taxa
        df = df.loc[df.sum(axis=1) > 10]
        return OmicsData(
            data=df,
            sample_metadata=data.sample_metadata,
            feature_metadata=data.feature_metadata,
            omics_type=self.name,
        )

    def quality_control(self, data: OmicsData) -> QCReport:
        df = data.data
        metrics = [
            QCMetric(name="n_taxa", value=df.shape[0], threshold=50, passed=df.shape[0] >= 50),
            QCMetric(name="n_samples", value=df.shape[1], threshold=10, passed=df.shape[1] >= 10),
        ]
        return QCReport(metrics=metrics, passed=all(m.passed for m in metrics))

    def normalize(self, data: OmicsData, params: AnalysisParams) -> OmicsData:
        method = params.parameters.get("method", "relative_abundance")
        df = data.data.copy()
        if method == "relative_abundance":
            df = df / df.sum()
        elif method == "clr":
            # Center log-ratio transformation
            df = df.replace(0, 1e-10)
            log_df = np.log(df)
            df = log_df.subtract(log_df.mean(axis=0), axis=1)
        return OmicsData(
            data=df,
            sample_metadata=data.sample_metadata,
            feature_metadata=data.feature_metadata,
            omics_type=self.name,
        )

    def analyze(self, data: OmicsData, params: AnalysisParams) -> AnalysisResult:
        return AnalysisResult(
            name=params.name, data=pd.DataFrame(), parameters=params.parameters, status="completed"
        )

    def visualize(self, result: AnalysisResult, params: dict | None = None) -> Visualization:
        return Visualization(
            name=f"{result.name}_plot",
            plot_type="stacked_bar",
            data=result.data.to_dict(),
            config=params or {},
        )

    def get_available_pipelines(self) -> list[Pipeline]:
        return [
            Pipeline(
                name="functional_profiling",
                description="Microbiome functional profiling",
                steps=["load", "qc", "normalize", "pathway_analysis", "visualization"],
            ),
            Pipeline(
                name="host_microbe",
                description="Host-microbiome interaction analysis",
                steps=["load", "correlation", "network", "interpretation"],
            ),
        ]

    def get_available_analyses(self) -> list[AnalysisDefinition]:
        return [
            AnalysisDefinition(name="pathway_abundance", description="Metabolic pathway abundance"),
            AnalysisDefinition(name="gene_family", description="Gene family abundance"),
            AnalysisDefinition(name="correlation", description="Host-microbiome correlation"),
            AnalysisDefinition(name="network", description="Microbiome interaction network"),
        ]

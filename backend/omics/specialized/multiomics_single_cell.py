"""Multiomics Single Cell Module.
=============================

Analysis module for single-cell multimodal data.
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


class MultiomicsSingleCellModule(OmicsModuleBase):
    """Module for single-cell multimodal omics analysis."""

    @property
    def name(self) -> str:
        return "multiomics_single_cell"

    @property
    def category(self) -> OmicsCategory:
        return OmicsCategory.SPECIALIZED

    @property
    def description(self) -> str:
        return "Single-cell multimodal analysis including CITE-seq, Multiome, and SHARE-seq"

    @property
    def supported_formats(self) -> list[str]:
        return ["h5ad", "h5mu", "mtx", "csv"]

    def load_data(self, source: DataSource) -> OmicsData:
        data = pd.read_csv(source.path, index_col=0) if source.format == "csv" else pd.DataFrame()
        return OmicsData(
            data=data,
            sample_metadata=pd.DataFrame(),
            feature_metadata=pd.DataFrame(),
            omics_type=self.name,
        )

    def preprocess(self, data: OmicsData) -> OmicsData:
        return data

    def quality_control(self, data: OmicsData) -> QCReport:
        df = data.data
        metrics = [
            QCMetric(name="n_cells", value=df.shape[1], threshold=500, passed=df.shape[1] >= 500),
            QCMetric(
                name="n_features", value=df.shape[0], threshold=100, passed=df.shape[0] >= 100
            ),
        ]
        return QCReport(metrics=metrics, passed=all(m.passed for m in metrics))

    def normalize(self, data: OmicsData, params: AnalysisParams) -> OmicsData:
        df = data.data.copy()
        df = np.log1p(df)
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
            plot_type="umap",
            data=result.data.to_dict(),
            config=params or {},
        )

    def get_available_pipelines(self) -> list[Pipeline]:
        return [
            Pipeline(
                name="cite_seq",
                description="CITE-seq analysis",
                steps=["load", "rna_processing", "adt_processing", "integration", "clustering"],
            ),
            Pipeline(
                name="multiome",
                description="10x Multiome ATAC+RNA analysis",
                steps=["load", "rna_processing", "atac_processing", "wnn", "clustering"],
            ),
            Pipeline(
                name="share_seq",
                description="SHARE-seq analysis",
                steps=["load", "processing", "integration", "trajectory"],
            ),
        ]

    def get_available_analyses(self) -> list[AnalysisDefinition]:
        return [
            AnalysisDefinition(name="wnn", description="Weighted nearest neighbor integration"),
            AnalysisDefinition(name="joint_clustering", description="Joint modality clustering"),
            AnalysisDefinition(name="modality_weight", description="Per-cell modality weighting"),
            AnalysisDefinition(name="gene_activity", description="Gene activity scores from ATAC"),
            AnalysisDefinition(
                name="protein_rna_correlation", description="Protein-RNA correlation"
            ),
        ]

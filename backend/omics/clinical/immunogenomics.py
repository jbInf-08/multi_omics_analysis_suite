"""
Immunogenomics Module - Immune system genomics
"""

from typing import Dict, List, Any, Optional

import numpy as np
import pandas as pd
from scipy.optimize import nnls
from backend.omics.base.omics_base import (
    OmicsModuleBase, OmicsCategory, OmicsData, QCReport, QCMetric,
    AnalysisParams, AnalysisResult, Visualization, Pipeline, AnalysisDefinition, DataSource,
)


class ImmunogenomicsModule(OmicsModuleBase):
    """Immunogenomics module for immune system analysis."""
    
    def __init__(self):
        super().__init__()
        self._version = "1.0.0"
        self._supported_formats = ["csv", "tsv", "vcf", "fasta"]
        self._pipelines = [
            Pipeline(name="immune_profiling", description="Immune cell profiling and repertoire analysis",
                steps=["load_data", "qc", "cell_deconvolution", "repertoire_analysis", "neoantigen_prediction"],
                default_parameters={"deconvolution_method": "cibersort"}),
            Pipeline(name="hla_typing", description="HLA genotyping and analysis",
                steps=["load_data", "hla_calling", "allele_annotation", "disease_association"],
                default_parameters={"resolution": "4-digit"}),
        ]
        self._analyses = [
            AnalysisDefinition(name="immune_deconvolution", description="Estimate immune cell composition",
                parameters={"method": {"type": "str", "default": "cibersort"}}, output_types=["table", "stacked_bar"]),
            AnalysisDefinition(name="tcr_repertoire", description="T-cell receptor repertoire analysis",
                parameters={"diversity_metrics": {"type": "list", "default": ["shannon", "clonality"]}}, output_types=["table", "distribution"]),
            AnalysisDefinition(name="neoantigen_prediction", description="Predict neoantigens",
                parameters={"binding_threshold": {"type": "float", "default": 500}}, output_types=["table"]),
            AnalysisDefinition(name="hla_typing", description="HLA allele calling",
                parameters={"resolution": {"type": "str", "default": "4-digit"}}, output_types=["table"]),
        ]
    
    @property
    def name(self) -> str: return "immunogenomics"
    @property
    def category(self) -> OmicsCategory: return OmicsCategory.CLINICAL
    @property
    def description(self) -> str: return "Immune system genomics, HLA typing, and immune repertoire analysis"
    
    def load_data(self, source: DataSource) -> OmicsData:
        if source.source_type == "file":
            df = pd.read_csv(source.path, sep="\t" if source.path.endswith(".tsv") else ",", index_col=0)
            return OmicsData(data=df.T, feature_names=df.index.tolist(), sample_names=df.columns.tolist(), data_type="immunogenomics", source=source)
        raise ValueError(f"Unsupported source: {source.source_type}")
    
    def preprocess(self, data: OmicsData, params: Optional[Dict[str, Any]] = None) -> OmicsData:
        processed = data.copy()
        processed.preprocessing_history.append("preprocess()")
        return processed
    
    def quality_control(self, data: OmicsData, params: Optional[Dict[str, Any]] = None) -> QCReport:
        metrics = [QCMetric(name="feature_count", value=len(data.feature_names), threshold=10)]
        return QCReport(passed=all(m.passed for m in metrics if m.passed is not None), metrics=metrics)
    
    def normalize(self, data: OmicsData, method: str = "tpm", params: Optional[Dict[str, Any]] = None) -> OmicsData:
        normalized = data.copy()
        normalized.preprocessing_history.append(f"normalize(method={method})")
        return normalized
    
    def analyze(self, data: OmicsData, params: AnalysisParams) -> AnalysisResult:
        if params.analysis_type == "immune_deconvolution":
            markers = {
                "T_cells": ["CD3E", "CD8A", "CD4", "IL2RA"],
                "B_cells": ["CD19", "MS4A1", "CD79A"],
                "NK_cells": ["NKG7", "GNLY", "KLRD1"],
                "Myeloid": ["CD14", "LYZ", "CSF1R"],
                "Macrophages": ["CD68", "CD163", "MSR1"],
                "Dendritic": ["FCER1A", "CST3"],
            }
            genes = list(data.feature_names)
            celltypes = list(markers.keys())
            g_index = {g: i for i, g in enumerate(genes)}
            m = np.ones((len(genes), len(celltypes)), dtype=float) * 0.05
            for j, ct in enumerate(celltypes):
                for mg in markers[ct]:
                    if mg in g_index:
                        m[g_index[mg], j] = 1.0

            per_sample: Dict[str, Dict[str, float]] = {}
            for i, sid in enumerate(data.sample_names):
                b = np.maximum(data.data.iloc[i].values.astype(float), 0.0)
                coef, _ = nnls(m, b)
                s = float(coef.sum()) + 1e-9
                coef = coef / s
                per_sample[sid] = {celltypes[k]: float(coef[k]) for k in range(len(celltypes))}

            return AnalysisResult(
                analysis_type=params.analysis_type,
                status="success",
                data={"cell_fractions": per_sample, "method": "nnls_marker_basis"},
                summary={"n_samples": len(per_sample), "n_celltypes": len(celltypes)},
            )
        return AnalysisResult(analysis_type=params.analysis_type, status="success", data={}, summary={})
    
    def visualize(self, result: AnalysisResult, plot_types: Optional[List[str]] = None) -> List[Visualization]: return []
    def get_available_pipelines(self) -> List[Pipeline]: return self._pipelines
    def get_available_analyses(self) -> List[AnalysisDefinition]: return self._analyses

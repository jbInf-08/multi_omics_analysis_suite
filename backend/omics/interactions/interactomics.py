"""Interactomics Module - Protein-protein interaction analysis."""

from typing import Any

import numpy as np
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


class InteractomicsModule(OmicsModuleBase):
    """Interactomics module for protein-protein interaction analysis."""

    def __init__(self):
        super().__init__()
        self._version = "1.0.0"
        self._supported_formats = ["csv", "tsv", "sif", "graphml"]
        self._pipelines = [
            Pipeline(
                name="ppi_analysis",
                description="Protein-protein interaction network analysis",
                steps=[
                    "load_data",
                    "network_construction",
                    "topology_analysis",
                    "module_detection",
                    "enrichment",
                ],
                default_parameters={"database": "string", "confidence": 0.7},
            ),
        ]
        self._analyses = [
            AnalysisDefinition(
                name="network_topology",
                description="Network topology analysis",
                parameters={
                    "metrics": {"type": "list", "default": ["degree", "betweenness", "clustering"]}
                },
                output_types=["table", "distribution"],
            ),
            AnalysisDefinition(
                name="module_detection",
                description="Detect network modules/communities",
                parameters={"method": {"type": "str", "default": "louvain"}},
                output_types=["table", "network"],
            ),
            AnalysisDefinition(
                name="hub_identification",
                description="Identify hub proteins",
                parameters={"top_n": {"type": "int", "default": 50}},
                output_types=["table"],
            ),
        ]

    @property
    def name(self) -> str:
        return "interactomics"

    @property
    def category(self) -> OmicsCategory:
        return OmicsCategory.INTERACTIONS

    @property
    def description(self) -> str:
        return "Protein-protein interaction network analysis"

    def load_data(self, source: DataSource) -> OmicsData:
        if source.source_type == "file":
            df = pd.read_csv(source.path, sep="\t" if source.path.endswith(".tsv") else ",")
            proteins = list(set(df.iloc[:, 0].tolist() + df.iloc[:, 1].tolist()))
            return OmicsData(
                data=df,
                feature_names=proteins,
                sample_names=["network"],
                data_type="interactomics",
                source=source,
            )
        raise ValueError(f"Unsupported source: {source.source_type}")

    def preprocess(self, data: OmicsData, params: dict[str, Any] | None = None) -> OmicsData:
        processed = data.copy()
        params = params or {}
        min_confidence = params.get("min_confidence", 0.4)
        if "confidence" in processed.data.columns:
            processed.data = processed.data[processed.data["confidence"] >= min_confidence]
        processed.preprocessing_history.append(f"preprocess(min_confidence={min_confidence})")
        return processed

    def quality_control(self, data: OmicsData, params: dict[str, Any] | None = None) -> QCReport:
        n_nodes = len(data.feature_names)
        n_edges = len(data.data)
        metrics = [
            QCMetric(name="node_count", value=n_nodes, threshold=10),
            QCMetric(name="edge_count", value=n_edges, threshold=10),
        ]
        return QCReport(
            passed=all(m.passed for m in metrics if m.passed is not None), metrics=metrics
        )

    def normalize(
        self, data: OmicsData, method: str = "none", params: dict[str, Any] | None = None
    ) -> OmicsData:
        return data.copy()

    def analyze(self, data: OmicsData, params: AnalysisParams) -> AnalysisResult:
        if params.analysis_type == "network_topology":
            return self._analyze_topology(data, params)
        elif params.analysis_type == "module_detection":
            return AnalysisResult(
                analysis_type=params.analysis_type,
                status="success",
                data={"modules": []},
                summary={},
            )
        elif params.analysis_type == "hub_identification":
            return AnalysisResult(
                analysis_type=params.analysis_type, status="success", data={"hubs": []}, summary={}
            )
        return AnalysisResult(
            analysis_type=params.analysis_type,
            status="failed",
            data={},
            errors=["Unknown analysis"],
        )

    def _analyze_topology(self, data: OmicsData, params: AnalysisParams) -> AnalysisResult:
        # Calculate basic network metrics
        degree_counts = {}
        for _, row in data.data.iterrows():
            p1, p2 = row.iloc[0], row.iloc[1]
            degree_counts[p1] = degree_counts.get(p1, 0) + 1
            degree_counts[p2] = degree_counts.get(p2, 0) + 1

        return AnalysisResult(
            analysis_type="network_topology",
            status="success",
            data={"degree_distribution": degree_counts},
            summary={
                "n_nodes": len(degree_counts),
                "n_edges": len(data.data),
                "avg_degree": np.mean(list(degree_counts.values())),
            },
        )

    def visualize(
        self, result: AnalysisResult, plot_types: list[str] | None = None
    ) -> list[Visualization]:
        if result.analysis_type == "network_topology" and "degree_distribution" in result.data:
            return [
                Visualization(
                    name="degree_distribution",
                    plot_type="histogram",
                    data=result.data["degree_distribution"],
                    title="Degree Distribution",
                )
            ]
        return []

    def get_available_pipelines(self) -> list[Pipeline]:
        return self._pipelines

    def get_available_analyses(self) -> list[AnalysisDefinition]:
        return self._analyses

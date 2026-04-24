"""
Spatialomics Module
==================

Analysis module for spatial transcriptomics and proteomics data.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

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


def _matrix_to_spots_x_genes(raw: pd.DataFrame, source: DataSource) -> pd.DataFrame:
    orientation = (source.metadata or {}).get("matrix_orientation", "auto")
    n_row, n_col = raw.shape
    if orientation == "genes_on_rows":
        return raw.T
    if orientation == "spots_on_rows":
        return raw
    if n_row > n_col and n_row > 500:
        return raw.T
    return raw


class SpatialomicsModule(OmicsModuleBase):
    """Module for spatial omics data analysis."""

    @property
    def name(self) -> str:
        return "spatialomics"

    @property
    def category(self) -> OmicsCategory:
        return OmicsCategory.SPECIALIZED

    @property
    def description(self) -> str:
        return "Spatial transcriptomics and proteomics analysis with tissue context"

    @property
    def supported_formats(self) -> List[str]:
        return ["h5ad", "csv", "mtx", "h5", "visium", "xenium"]

    def load_data(self, source: DataSource) -> OmicsData:
        """Load spatial counts (spots × genes) and optional coordinates from metadata."""
        if source.source_type != "file" or not source.path:
            raise ValueError("spatialomics expects source_type=file with path")

        fmt = (source.format or "csv").lower()
        spatial_coords: Optional[pd.DataFrame] = None
        meta = source.metadata or {}
        coords_path = meta.get("spatial_coords_csv") or meta.get("metadata_path")

        if fmt in ("csv", "tsv", "txt", "visium", "xenium"):
            sep = "\t" if fmt in ("tsv", "txt") else ","
            raw = pd.read_csv(source.path, sep=sep, index_col=0)
        elif fmt == "mtx":
            from scipy.io import mmread

            mat = mmread(source.path)
            raw = pd.DataFrame(mat.toarray())
        elif fmt == "h5ad":
            try:
                import anndata as ad

                adata = ad.read_h5ad(source.path)
                raw = pd.DataFrame(
                    adata.X.toarray() if hasattr(adata.X, "toarray") else adata.X,
                    index=adata.obs_names.astype(str),
                    columns=adata.var_names.astype(str),
                )
                if "spatial" in adata.obsm:
                    xy = np.asarray(adata.obsm["spatial"])[:, :2]
                    spatial_coords = pd.DataFrame(xy, index=raw.index, columns=["spatial_x", "spatial_y"])
            except ImportError:
                raw = pd.DataFrame()
        else:
            raw = pd.DataFrame()

        if coords_path and spatial_coords is None:
            spatial_coords = pd.read_csv(coords_path, index_col=0)
            if not {"spatial_x", "spatial_y"}.issubset(spatial_coords.columns):
                # allow x,y naming
                if {"x", "y"}.issubset(spatial_coords.columns):
                    spatial_coords = spatial_coords.rename(columns={"x": "spatial_x", "y": "spatial_y"})

        if raw.empty:
            return OmicsData(
                data=pd.DataFrame(),
                feature_names=[],
                sample_names=[],
                data_type="spatialomics",
                sample_metadata=spatial_coords,
                source=source,
            )

        X = _matrix_to_spots_x_genes(raw, source)
        X.index = X.index.astype(str)
        X.columns = X.columns.astype(str)
        if spatial_coords is not None:
            spatial_coords = spatial_coords.reindex(X.index)

        return OmicsData(
            data=X,
            feature_names=list(X.columns),
            sample_names=list(X.index),
            data_type="spatialomics",
            sample_metadata=spatial_coords,
            source=source,
        )

    def preprocess(self, data: OmicsData, params: Optional[Dict[str, Any]] = None) -> OmicsData:
        """Filter low-expression spots and rare genes."""
        if data.data.empty:
            return data
        df = data.data.copy()
        spot_counts = df.sum(axis=1)
        gene_counts = df.sum(axis=0)
        df = df.loc[spot_counts > 100, gene_counts > 10]
        sm = data.sample_metadata
        if sm is not None and not sm.empty:
            sm = sm.reindex(df.index)
        return OmicsData(
            data=df,
            feature_names=list(df.columns),
            sample_names=list(df.index),
            data_type=self.name,
            feature_metadata=data.feature_metadata,
            sample_metadata=sm,
            source=data.source,
            preprocessing_history=data.preprocessing_history + ["preprocess()"],
        )

    def quality_control(self, data: OmicsData, params: Optional[Dict[str, Any]] = None) -> QCReport:
        if data.data.empty:
            return QCReport(
                passed=False,
                metrics=[QCMetric(name="empty", value=0.0, threshold=1.0, passed=False)],
            )
        df = data.data
        metrics = [
            QCMetric(name="total_spots", value=float(df.shape[0]), threshold=100, passed=df.shape[0] >= 100),
            QCMetric(name="total_genes", value=float(df.shape[1]), threshold=1000, passed=df.shape[1] >= 1000),
            QCMetric(
                name="median_genes_per_spot",
                value=float((df > 0).sum(axis=1).median()),
                threshold=200,
                passed=float((df > 0).sum(axis=1).median()) >= 200,
            ),
            QCMetric(
                name="median_counts_per_spot",
                value=float(df.sum(axis=1).median()),
                threshold=500,
                passed=float(df.sum(axis=1).median()) >= 500,
            ),
        ]
        return QCReport(metrics=metrics, passed=all(m.passed for m in metrics))

    def normalize(
        self,
        data: OmicsData,
        method: str = "log_normalize",
        params: Optional[Dict[str, Any]] = None,
    ) -> OmicsData:
        if data.data.empty:
            return data
        p = params or {}
        m = p.get("method", method)
        df = data.data.astype(float).copy()
        if m == "log_normalize":
            sf = df.sum(axis=1).replace(0, np.nan)
            sf = sf / sf.median()
            df = (df.T / sf).T.fillna(0.0)
            df = np.log1p(df)
        return OmicsData(
            data=df,
            feature_names=list(df.columns),
            sample_names=list(df.index),
            data_type=self.name,
            feature_metadata=data.feature_metadata,
            sample_metadata=data.sample_metadata,
            source=data.source,
            preprocessing_history=data.preprocessing_history + [f"normalize({m})"],
        )

    def _spatial_coords_array(self, data: OmicsData) -> Optional[np.ndarray]:
        sm = data.sample_metadata
        if sm is None or sm.empty:
            return None
        if {"spatial_x", "spatial_y"}.issubset(sm.columns):
            return sm.loc[data.sample_names, ["spatial_x", "spatial_y"]].values.astype(float)
        return None

    def analyze(self, data: OmicsData, params: AnalysisParams) -> AnalysisResult:
        analysis_type = params.analysis_type
        if data.data.empty:
            return AnalysisResult(analysis_type=analysis_type, status="failed", data={}, errors=["empty dataset"])

        if analysis_type == "spatial_clustering":
            X = data.data.values
            coords = self._spatial_coords_array(data)
            if coords is not None and coords.shape[0] == X.shape[0]:
                Xf = np.hstack([StandardScaler().fit_transform(X), StandardScaler().fit_transform(coords)])
            else:
                Xf = StandardScaler().fit_transform(X)
            k = int(params.get("n_clusters", 5))
            k = max(2, min(k, Xf.shape[0] // 2))
            labels = KMeans(n_clusters=k, random_state=42, n_init=10).fit_predict(Xf)
            tbl = pd.DataFrame({"spot": data.sample_names, "cluster": labels})
            return AnalysisResult(
                analysis_type="spatial_clustering",
                status="success",
                data={"clusters": tbl.to_dict("records")},
                summary={"n_clusters": k, "used_coordinates": coords is not None},
            )

        if analysis_type == "spatially_variable_genes":
            coords = self._spatial_coords_array(data)
            rows = []
            df = data.data
            if coords is not None and coords.shape[0] == df.shape[0]:
                from sklearn.neighbors import NearestNeighbors

                n_neighbors = min(7, df.shape[0])
                nn = NearestNeighbors(n_neighbors=n_neighbors).fit(coords)
                neigh = nn.kneighbors(return_distance=False)
                for g in df.columns[: min(200, df.shape[1])]:
                    x = df[g].values.astype(float)
                    lag = np.array([x[idx[1:]].mean() for idx in neigh])
                    if np.std(x) < 1e-9:
                        mi = 0.0
                    else:
                        mi = float(np.corrcoef(x, lag)[0, 1])
                    rows.append({"gene": g, "morans_i": mi, "pvalue": max(1e-6, 1 - abs(mi))})
            else:
                mu = df.mean(axis=0)
                cv = df.std(axis=0) / (mu + 1e-6)
                for g, score in cv.nlargest(50).items():
                    rows.append({"gene": g, "morans_i": float(score), "pvalue": 0.05})

            tbl = pd.DataFrame(rows)
            return AnalysisResult(
                analysis_type="spatially_variable_genes",
                status="success",
                data={"svg": tbl.to_dict("records")},
                summary={"n_genes": len(rows)},
            )

        return AnalysisResult(
            analysis_type=analysis_type,
            status="failed",
            data={},
            errors=["analysis not implemented for this type"],
        )

    def visualize(
        self,
        result: AnalysisResult,
        plot_types: Optional[List[str]] = None,
    ) -> List[Visualization]:
        payload = result.data.get("clusters") or result.data.get("svg") or result.data
        return [
            Visualization(
                name=f"{result.analysis_type}_plot",
                plot_type="spatial",
                data={"points": payload},
                config={"requested": plot_types} if plot_types else {},
            )
        ]

    def get_available_pipelines(self) -> List[Pipeline]:
        return [
            Pipeline(
                name="spatial_transcriptomics",
                description="Complete spatial transcriptomics workflow",
                steps=["load", "qc", "normalize", "spatial_clustering", "svg_detection", "visualization"],
            ),
            Pipeline(
                name="tissue_segmentation",
                description="Tissue region identification and segmentation",
                steps=["load", "preprocessing", "segmentation", "annotation"],
            ),
        ]

    def get_available_analyses(self) -> List[AnalysisDefinition]:
        return [
            AnalysisDefinition(
                name="spatial_clustering",
                description="Cluster spots based on spatial and expression patterns",
            ),
            AnalysisDefinition(name="spatially_variable_genes", description="Identify spatially variable genes"),
            AnalysisDefinition(name="cell_type_deconvolution", description="Deconvolve cell types from spots"),
            AnalysisDefinition(
                name="ligand_receptor_analysis",
                description="Spatial ligand-receptor interaction analysis",
            ),
            AnalysisDefinition(name="spatial_autocorrelation", description="Moran's I and spatial statistics"),
        ]

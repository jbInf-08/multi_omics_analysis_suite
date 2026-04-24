"""
Transcriptomics Module
======================

Comprehensive RNA expression analysis including:
- Differential expression analysis
- Gene set enrichment
- Alternative splicing
- RNA-seq quantification
- Single-cell RNA-seq
"""

from typing import Dict, List, Any, Optional
from pathlib import Path
import logging

import numpy as np
import pandas as pd
from scipy import stats

from backend.omics.base.omics_base import (
    OmicsModuleBase,
    OmicsCategory,
    OmicsData,
    QCReport,
    QCMetric,
    AnalysisParams,
    AnalysisResult,
    Visualization,
    Pipeline,
    AnalysisDefinition,
    DataSource,
)


logger = logging.getLogger(__name__)


class TranscriptomicsModule(OmicsModuleBase):
    """
    Transcriptomics analysis module.
    
    Supports analysis of RNA expression data including:
    - Bulk RNA-seq
    - Single-cell RNA-seq
    - Microarray
    - Alternative splicing
    """
    
    def __init__(self):
        super().__init__()
        self._version = "1.0.0"
        self._supported_formats = ["csv", "tsv", "h5ad", "mtx", "gct"]
        
        self._pipelines = [
            Pipeline(
                name="differential_expression",
                description="Differential gene expression analysis pipeline",
                steps=[
                    "load_data",
                    "quality_control",
                    "normalization",
                    "batch_correction",
                    "differential_analysis",
                    "multiple_testing_correction",
                    "visualization",
                ],
                default_parameters={
                    "normalization": "tpm",
                    "method": "deseq2",
                    "fdr_threshold": 0.05,
                    "log2fc_threshold": 1.0,
                },
            ),
            Pipeline(
                name="gene_set_enrichment",
                description="Gene set enrichment analysis pipeline",
                steps=[
                    "load_data",
                    "rank_genes",
                    "gsea_analysis",
                    "pathway_visualization",
                ],
                default_parameters={
                    "database": "msigdb",
                    "collection": "hallmark",
                    "permutations": 1000,
                },
            ),
            Pipeline(
                name="single_cell_analysis",
                description="Single-cell RNA-seq analysis pipeline",
                steps=[
                    "load_data",
                    "quality_control",
                    "normalization",
                    "feature_selection",
                    "dimensionality_reduction",
                    "clustering",
                    "marker_detection",
                    "visualization",
                ],
                default_parameters={
                    "n_hvg": 2000,
                    "n_pcs": 50,
                    "resolution": 1.0,
                },
            ),
        ]
        
        self._analyses = [
            AnalysisDefinition(
                name="differential_expression",
                description="Identify differentially expressed genes",
                parameters={
                    "method": {"type": "str", "default": "deseq2", "description": "DE method (deseq2, limma, edger)"},
                    "group_column": {"type": "str", "default": "condition", "description": "Grouping column"},
                    "fdr_threshold": {"type": "float", "default": 0.05, "description": "FDR threshold"},
                    "log2fc_threshold": {"type": "float", "default": 1.0, "description": "Log2 fold change threshold"},
                },
                output_types=["table", "volcano_plot", "ma_plot", "heatmap"],
            ),
            AnalysisDefinition(
                name="gsea",
                description="Gene Set Enrichment Analysis",
                parameters={
                    "ranking_metric": {"type": "str", "default": "signal_to_noise", "description": "Gene ranking metric"},
                    "database": {"type": "str", "default": "msigdb", "description": "Gene set database"},
                    "n_permutations": {"type": "int", "default": 1000, "description": "Number of permutations"},
                },
                output_types=["table", "enrichment_plot"],
            ),
            AnalysisDefinition(
                name="pca",
                description="Principal Component Analysis",
                parameters={
                    "n_components": {"type": "int", "default": 50, "description": "Number of components"},
                    "scale": {"type": "bool", "default": True, "description": "Scale features"},
                },
                output_types=["table", "pca_plot", "variance_plot"],
            ),
            AnalysisDefinition(
                name="clustering",
                description="Sample/cell clustering",
                parameters={
                    "method": {"type": "str", "default": "leiden", "description": "Clustering method"},
                    "resolution": {"type": "float", "default": 1.0, "description": "Resolution parameter"},
                },
                output_types=["labels", "umap_plot"],
            ),
        ]
    
    @property
    def name(self) -> str:
        return "transcriptomics"
    
    @property
    def category(self) -> OmicsCategory:
        return OmicsCategory.CORE
    
    @property
    def description(self) -> str:
        return "RNA expression analysis including differential expression, GSEA, and single-cell analysis"
    
    def load_data(self, source: DataSource) -> OmicsData:
        """Load transcriptomics data."""
        logger.info(f"Loading transcriptomics data from {source.source_type}")
        
        if source.source_type == "file":
            file_path = Path(source.path)
            format_type = source.format or file_path.suffix.lstrip(".")
            
            if format_type in ["csv", "tsv"]:
                sep = "\t" if format_type == "tsv" else ","
                df = pd.read_csv(file_path, sep=sep, index_col=0)
                return self._dataframe_to_omics_data(df, source)
            elif format_type == "gct":
                return self._load_gct(file_path, source)
            else:
                raise ValueError(f"Unsupported format: {format_type}")
        else:
            raise ValueError(f"Unsupported source type: {source.source_type}")
    
    def _load_gct(self, file_path: Path, source: DataSource) -> OmicsData:
        """Load GCT format file."""
        df = pd.read_csv(file_path, sep="\t", skiprows=2, index_col=0)
        if "Description" in df.columns:
            feature_metadata = df[["Description"]]
            df = df.drop(columns=["Description"])
        else:
            feature_metadata = None
        
        return OmicsData(
            data=df.T,  # Transpose to samples x features
            feature_names=df.index.tolist(),
            sample_names=df.columns.tolist(),
            data_type="transcriptomics",
            feature_metadata=feature_metadata,
            source=source,
        )
    
    def _dataframe_to_omics_data(self, df: pd.DataFrame, source: DataSource) -> OmicsData:
        """Convert expression DataFrame to OmicsData."""
        # Assume rows are genes, columns are samples
        return OmicsData(
            data=df.T,  # Transpose to samples x features
            feature_names=df.index.tolist(),
            sample_names=df.columns.tolist(),
            data_type="transcriptomics",
            source=source,
        )
    
    def preprocess(
        self,
        data: OmicsData,
        params: Optional[Dict[str, Any]] = None,
    ) -> OmicsData:
        """Preprocess transcriptomics data."""
        params = params or {}
        processed = data.copy()
        
        # Filter low-expressed genes
        min_count = params.get("min_count", 10)
        min_samples = params.get("min_samples", 3)
        
        # Count samples with expression above threshold
        expressed = (processed.data > min_count).sum(axis=0)
        keep_genes = expressed >= min_samples
        
        processed.data = processed.data.loc[:, keep_genes]
        processed.feature_names = [f for f, k in zip(processed.feature_names, keep_genes) if k]
        
        processed.preprocessing_history.append(
            f"preprocess(min_count={min_count}, min_samples={min_samples})"
        )
        
        return processed
    
    def quality_control(
        self,
        data: OmicsData,
        params: Optional[Dict[str, Any]] = None,
    ) -> QCReport:
        """Run quality control on transcriptomics data."""
        params = params or {}
        metrics = []
        issues = []
        warnings = []
        recommendations = []
        
        # Check number of genes
        n_genes = len(data.feature_names)
        metrics.append(QCMetric(
            name="gene_count",
            value=n_genes,
            threshold=5000,
            description="Number of genes/features",
        ))
        
        # Check number of samples
        n_samples = len(data.sample_names)
        metrics.append(QCMetric(
            name="sample_count",
            value=n_samples,
            threshold=3,
            description="Number of samples",
        ))
        
        # Check for zero-expressed genes
        zero_genes = (data.data.sum(axis=0) == 0).sum()
        zero_ratio = zero_genes / n_genes if n_genes > 0 else 0
        metrics.append(QCMetric(
            name="zero_expression_ratio",
            value=1 - zero_ratio,
            threshold=0.5,
            description="Ratio of genes with non-zero expression",
        ))
        
        # Check library sizes
        lib_sizes = data.data.sum(axis=1)
        cv_lib_size = lib_sizes.std() / lib_sizes.mean() if lib_sizes.mean() > 0 else float("inf")
        metrics.append(QCMetric(
            name="library_size_cv",
            value=1 - min(cv_lib_size, 1),
            threshold=0.5,
            description="Library size consistency (1 - CV)",
        ))
        
        if cv_lib_size > 1:
            warnings.append("High variability in library sizes")
            recommendations.append("Consider size factor normalization")
        
        if zero_ratio > 0.5:
            issues.append("More than 50% of genes have zero expression")
            recommendations.append("Filter lowly expressed genes")
        
        passed = all(m.passed for m in metrics if m.passed is not None)
        
        return QCReport(
            passed=passed,
            metrics=metrics,
            issues=issues,
            warnings=warnings,
            recommendations=recommendations,
            details={
                "median_library_size": float(lib_sizes.median()),
                "mean_genes_per_sample": float((data.data > 0).sum(axis=1).mean()),
            },
        )
    
    def normalize(
        self,
        data: OmicsData,
        method: str = "tpm",
        params: Optional[Dict[str, Any]] = None,
    ) -> OmicsData:
        """Normalize transcriptomics data."""
        params = params or {}
        normalized = data.copy()
        
        if method == "tpm":
            # TPM normalization (simplified without gene lengths)
            rpm = normalized.data.div(normalized.data.sum(axis=1), axis=0) * 1e6
            normalized.data = rpm
        
        elif method == "cpm":
            # Counts per million
            cpm = normalized.data.div(normalized.data.sum(axis=1), axis=0) * 1e6
            normalized.data = cpm
        
        elif method == "log2":
            # Log2 transformation with pseudocount
            pseudocount = params.get("pseudocount", 1)
            normalized.data = np.log2(normalized.data + pseudocount)
        
        elif method == "quantile":
            # Quantile normalization
            normalized.data = self._quantile_normalize(normalized.data)
        
        elif method == "zscore":
            # Z-score normalization
            normalized.data = (normalized.data - normalized.data.mean()) / normalized.data.std()
        
        normalized.preprocessing_history.append(f"normalize(method={method})")
        return normalized
    
    def _quantile_normalize(self, df: pd.DataFrame) -> pd.DataFrame:
        """Perform quantile normalization."""
        rank_mean = df.stack().groupby(df.rank(method='first').stack().astype(int)).mean()
        return df.rank(method='min').stack().astype(int).map(rank_mean).unstack()
    
    def analyze(
        self,
        data: OmicsData,
        params: AnalysisParams,
    ) -> AnalysisResult:
        """Run transcriptomics analysis."""
        analysis_type = params.analysis_type
        
        if analysis_type == "differential_expression":
            return self._analyze_differential_expression(data, params)
        elif analysis_type == "gsea":
            return self._analyze_gsea(data, params)
        elif analysis_type == "pca":
            return self._analyze_pca(data, params)
        elif analysis_type == "clustering":
            return self._analyze_clustering(data, params)
        else:
            return AnalysisResult(
                analysis_type=analysis_type,
                status="failed",
                data={},
                errors=[f"Unknown analysis type: {analysis_type}"],
            )
    
    def _analyze_differential_expression(self, data: OmicsData, params: AnalysisParams) -> AnalysisResult:
        """Run differential expression analysis."""
        fdr_threshold = params.get("fdr_threshold", 0.05)
        log2fc_threshold = params.get("log2fc_threshold", 1.0)
        
        # Simplified t-test based DE (in production would use DESeq2/limma)
        results = []
        
        if data.sample_metadata is not None and "condition" in data.sample_metadata.columns:
            conditions = data.sample_metadata["condition"].unique()
            if len(conditions) >= 2:
                group1 = data.sample_metadata[data.sample_metadata["condition"] == conditions[0]].index
                group2 = data.sample_metadata[data.sample_metadata["condition"] == conditions[1]].index
                
                for gene in data.feature_names:
                    if gene in data.data.columns:
                        g1_values = data.data.loc[group1, gene]
                        g2_values = data.data.loc[group2, gene]
                        
                        # Calculate statistics
                        mean1, mean2 = g1_values.mean(), g2_values.mean()
                        log2fc = np.log2((mean2 + 1) / (mean1 + 1))
                        
                        # T-test
                        t_stat, p_value = stats.ttest_ind(g1_values, g2_values)
                        
                        results.append({
                            "gene": gene,
                            "log2FoldChange": log2fc,
                            "pvalue": p_value,
                            "baseMean": (mean1 + mean2) / 2,
                        })
        
        if results:
            de_df = pd.DataFrame(results)
            # FDR correction
            from scipy.stats import false_discovery_control
            de_df["padj"] = false_discovery_control(de_df["pvalue"].values, method="bh") if len(de_df) > 0 else []
            
            # Classify significance
            de_df["significant"] = (de_df["padj"] < fdr_threshold) & (abs(de_df["log2FoldChange"]) > log2fc_threshold)
            
            n_up = ((de_df["significant"]) & (de_df["log2FoldChange"] > 0)).sum()
            n_down = ((de_df["significant"]) & (de_df["log2FoldChange"] < 0)).sum()
        else:
            de_df = pd.DataFrame()
            n_up, n_down = 0, 0
        
        result = AnalysisResult(
            analysis_type="differential_expression",
            status="success",
            data={"de_results": de_df.to_dict("records") if not de_df.empty else []},
            summary={
                "n_genes_tested": len(results),
                "n_significant": int(de_df["significant"].sum()) if not de_df.empty else 0,
                "n_upregulated": int(n_up),
                "n_downregulated": int(n_down),
            },
            metrics={
                "fdr_threshold": fdr_threshold,
                "log2fc_threshold": log2fc_threshold,
            },
        )
        
        if not de_df.empty:
            result.add_table("de_results", de_df)
        
        return result
    
    def _analyze_gsea(self, data: OmicsData, params: AnalysisParams) -> AnalysisResult:
        """Preranked-style pathway enrichment (variance-based ranking if none supplied)."""
        from backend.omics._pathway_reference import PATHWAY_GENE_SETS, preranked_gsea_like

        genes = [str(g) for g in data.feature_names]
        ranks = params.get("gene_scores")
        if ranks is None or len(ranks) != len(genes):
            ranks = data.data.var(axis=0).values.astype(float).tolist()
        n_perm = int(params.get("n_permutations", 200))
        enriched = preranked_gsea_like(genes, ranks, PATHWAY_GENE_SETS, n_perm=n_perm, seed=42)
        sig = [r for r in enriched if r["pvalue"] <= float(params.get("pvalue_cutoff", 0.2))]

        return AnalysisResult(
            analysis_type="gsea",
            status="success",
            data={"enriched_pathways": enriched},
            summary={
                "n_gene_sets_tested": len(PATHWAY_GENE_SETS),
                "n_significant": len(sig),
            },
        )
    
    def _analyze_pca(self, data: OmicsData, params: AnalysisParams) -> AnalysisResult:
        """Run PCA analysis."""
        from sklearn.decomposition import PCA
        from sklearn.preprocessing import StandardScaler
        
        n_components = params.get("n_components", 50)
        scale = params.get("scale", True)
        
        # Prepare data
        X = data.data.values
        
        if scale:
            scaler = StandardScaler()
            X = scaler.fit_transform(X)
        
        # Run PCA
        n_components = min(n_components, X.shape[0], X.shape[1])
        pca = PCA(n_components=n_components)
        pca_result = pca.fit_transform(X)
        
        # Create result DataFrame
        pca_df = pd.DataFrame(
            pca_result,
            index=data.sample_names,
            columns=[f"PC{i+1}" for i in range(n_components)],
        )
        
        result = AnalysisResult(
            analysis_type="pca",
            status="success",
            data={
                "pca_coordinates": pca_df.to_dict("records"),
                "explained_variance": pca.explained_variance_ratio_.tolist(),
            },
            summary={
                "n_components": n_components,
                "total_variance_explained": float(pca.explained_variance_ratio_.sum()),
            },
        )
        result.add_table("pca_results", pca_df)
        
        return result
    
    def _analyze_clustering(self, data: OmicsData, params: AnalysisParams) -> AnalysisResult:
        """Run clustering analysis."""
        from sklearn.cluster import KMeans
        
        n_clusters = params.get("n_clusters", 5)
        
        # Simple k-means clustering
        kmeans = KMeans(n_clusters=n_clusters, random_state=42)
        labels = kmeans.fit_predict(data.data.values)
        
        return AnalysisResult(
            analysis_type="clustering",
            status="success",
            data={"cluster_labels": labels.tolist()},
            summary={"n_clusters": n_clusters},
        )
    
    def visualize(
        self,
        result: AnalysisResult,
        plot_types: Optional[List[str]] = None,
    ) -> List[Visualization]:
        """Generate transcriptomics visualizations."""
        visualizations = []
        
        if result.analysis_type == "differential_expression":
            # Volcano plot
            if "de_results" in result.data and result.data["de_results"]:
                visualizations.append(Visualization(
                    name="volcano_plot",
                    plot_type="scatter",
                    data={
                        "x": [r["log2FoldChange"] for r in result.data["de_results"]],
                        "y": [-np.log10(r["pvalue"]) for r in result.data["de_results"]],
                        "text": [r["gene"] for r in result.data["de_results"]],
                    },
                    title="Volcano Plot",
                    config={"xaxis_title": "Log2 Fold Change", "yaxis_title": "-Log10 P-value"},
                ))
        
        elif result.analysis_type == "pca":
            if "pca_coordinates" in result.data:
                coords = result.data["pca_coordinates"]
                visualizations.append(Visualization(
                    name="pca_plot",
                    plot_type="scatter",
                    data={
                        "x": [c["PC1"] for c in coords],
                        "y": [c["PC2"] for c in coords],
                    },
                    title="PCA Plot",
                    config={"xaxis_title": "PC1", "yaxis_title": "PC2"},
                ))
        
        return visualizations
    
    def get_available_pipelines(self) -> List[Pipeline]:
        return self._pipelines
    
    def get_available_analyses(self) -> List[AnalysisDefinition]:
        return self._analyses

"""
Proteomics Module
=================

Comprehensive protein analysis including:
- Protein quantification
- Post-translational modifications
- Protein-protein interactions
- Structural analysis
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


class ProteomicsModule(OmicsModuleBase):
    """
    Proteomics analysis module.
    
    Supports analysis of protein data including:
    - Mass spectrometry data
    - Protein expression quantification
    - PTM analysis
    - Protein-protein interactions
    """
    
    def __init__(self):
        super().__init__()
        self._version = "1.0.0"
        self._supported_formats = ["csv", "tsv", "mzML", "mzXML", "maxquant"]
        
        self._pipelines = [
            Pipeline(
                name="protein_quantification",
                description="Protein quantification from mass spectrometry data",
                steps=[
                    "load_data",
                    "quality_control",
                    "imputation",
                    "normalization",
                    "differential_analysis",
                    "visualization",
                ],
                default_parameters={
                    "normalization": "median",
                    "imputation": "knn",
                    "fdr_threshold": 0.05,
                },
            ),
            Pipeline(
                name="ptm_analysis",
                description="Post-translational modification analysis",
                steps=[
                    "load_data",
                    "site_localization",
                    "quantification",
                    "differential_analysis",
                    "motif_analysis",
                ],
                default_parameters={
                    "localization_threshold": 0.75,
                    "modification_type": "phosphorylation",
                },
            ),
        ]
        
        self._analyses = [
            AnalysisDefinition(
                name="differential_abundance",
                description="Identify differentially abundant proteins",
                parameters={
                    "method": {"type": "str", "default": "limma", "description": "Statistical method"},
                    "fdr_threshold": {"type": "float", "default": 0.05, "description": "FDR threshold"},
                    "log2fc_threshold": {"type": "float", "default": 1.0, "description": "Log2 FC threshold"},
                },
                output_types=["table", "volcano_plot", "heatmap"],
            ),
            AnalysisDefinition(
                name="protein_correlation",
                description="Protein co-expression/correlation analysis",
                parameters={
                    "method": {"type": "str", "default": "pearson", "description": "Correlation method"},
                    "threshold": {"type": "float", "default": 0.7, "description": "Correlation threshold"},
                },
                output_types=["table", "network"],
            ),
            AnalysisDefinition(
                name="pathway_enrichment",
                description="Protein pathway enrichment analysis",
                parameters={
                    "database": {"type": "str", "default": "reactome", "description": "Pathway database"},
                    "method": {"type": "str", "default": "ora", "description": "Enrichment method"},
                },
                output_types=["table", "barplot"],
            ),
        ]
    
    @property
    def name(self) -> str:
        return "proteomics"
    
    @property
    def category(self) -> OmicsCategory:
        return OmicsCategory.CORE
    
    @property
    def description(self) -> str:
        return "Protein expression and modification analysis from mass spectrometry data"
    
    def load_data(self, source: DataSource) -> OmicsData:
        """Load proteomics data."""
        logger.info(f"Loading proteomics data from {source.source_type}")
        
        if source.source_type == "file":
            file_path = Path(source.path)
            format_type = source.format or file_path.suffix.lstrip(".")
            
            if format_type in ["csv", "tsv"]:
                sep = "\t" if format_type == "tsv" else ","
                df = pd.read_csv(file_path, sep=sep, index_col=0)
                return self._dataframe_to_omics_data(df, source)
            else:
                raise ValueError(f"Unsupported format: {format_type}")
        else:
            raise ValueError(f"Unsupported source type: {source.source_type}")
    
    def _dataframe_to_omics_data(self, df: pd.DataFrame, source: DataSource) -> OmicsData:
        """Convert protein abundance DataFrame to OmicsData."""
        return OmicsData(
            data=df.T,
            feature_names=df.index.tolist(),
            sample_names=df.columns.tolist(),
            data_type="proteomics",
            source=source,
        )
    
    def preprocess(
        self,
        data: OmicsData,
        params: Optional[Dict[str, Any]] = None,
    ) -> OmicsData:
        """Preprocess proteomics data."""
        params = params or {}
        processed = data.copy()
        
        # Filter proteins with too many missing values
        max_missing = params.get("max_missing_ratio", 0.5)
        missing_ratio = processed.data.isna().sum(axis=0) / len(processed.sample_names)
        keep_proteins = missing_ratio <= max_missing
        
        processed.data = processed.data.loc[:, keep_proteins]
        processed.feature_names = [f for f, k in zip(processed.feature_names, keep_proteins) if k]
        
        # Imputation
        imputation_method = params.get("imputation", "min")
        if imputation_method == "min":
            # Replace missing with minimum observed value
            min_val = processed.data.min().min()
            processed.data = processed.data.fillna(min_val)
        elif imputation_method == "knn":
            # KNN imputation would go here
            processed.data = processed.data.fillna(processed.data.mean())
        
        processed.preprocessing_history.append(
            f"preprocess(max_missing={max_missing}, imputation={imputation_method})"
        )
        
        return processed
    
    def quality_control(
        self,
        data: OmicsData,
        params: Optional[Dict[str, Any]] = None,
    ) -> QCReport:
        """Run quality control on proteomics data."""
        params = params or {}
        metrics = []
        issues = []
        warnings = []
        recommendations = []
        
        n_proteins = len(data.feature_names)
        n_samples = len(data.sample_names)
        
        metrics.append(QCMetric(
            name="protein_count",
            value=n_proteins,
            threshold=500,
            description="Number of proteins quantified",
        ))
        
        metrics.append(QCMetric(
            name="sample_count",
            value=n_samples,
            threshold=3,
            description="Number of samples",
        ))
        
        # Missing value ratio
        missing_ratio = data.data.isna().sum().sum() / data.data.size if data.data.size > 0 else 0
        metrics.append(QCMetric(
            name="data_completeness",
            value=1 - missing_ratio,
            threshold=0.5,
            description="Data completeness (1 - missing ratio)",
        ))
        
        # CV of total intensity
        total_intensity = data.data.sum(axis=1)
        cv = total_intensity.std() / total_intensity.mean() if total_intensity.mean() > 0 else float("inf")
        metrics.append(QCMetric(
            name="intensity_cv",
            value=max(0, 1 - cv),
            threshold=0.5,
            description="Total intensity consistency",
        ))
        
        if missing_ratio > 0.5:
            issues.append("High proportion of missing values")
            recommendations.append("Consider stricter filtering or imputation")
        
        if cv > 1:
            warnings.append("High variability in total protein intensity")
            recommendations.append("Check for batch effects or sample loading")
        
        passed = all(m.passed for m in metrics if m.passed is not None)
        
        return QCReport(
            passed=passed,
            metrics=metrics,
            issues=issues,
            warnings=warnings,
            recommendations=recommendations,
        )
    
    def normalize(
        self,
        data: OmicsData,
        method: str = "median",
        params: Optional[Dict[str, Any]] = None,
    ) -> OmicsData:
        """Normalize proteomics data."""
        params = params or {}
        normalized = data.copy()
        
        if method == "median":
            # Median normalization
            medians = normalized.data.median(axis=1)
            global_median = medians.median()
            scale_factors = global_median / medians
            normalized.data = normalized.data.mul(scale_factors, axis=0)
        
        elif method == "quantile":
            # Quantile normalization
            rank_mean = normalized.data.stack().groupby(
                normalized.data.rank(method='first').stack().astype(int)
            ).mean()
            normalized.data = normalized.data.rank(method='min').stack().astype(int).map(rank_mean).unstack()
        
        elif method == "log2":
            pseudocount = params.get("pseudocount", 1)
            normalized.data = np.log2(normalized.data + pseudocount)
        
        elif method == "vsn":
            # Variance stabilizing normalization (simplified)
            normalized.data = np.log2(normalized.data + 1)
            normalized.data = (normalized.data - normalized.data.mean()) / normalized.data.std()
        
        normalized.preprocessing_history.append(f"normalize(method={method})")
        return normalized
    
    def analyze(
        self,
        data: OmicsData,
        params: AnalysisParams,
    ) -> AnalysisResult:
        """Run proteomics analysis."""
        analysis_type = params.analysis_type
        
        if analysis_type == "differential_abundance":
            return self._analyze_differential_abundance(data, params)
        elif analysis_type == "protein_correlation":
            return self._analyze_correlation(data, params)
        elif analysis_type == "pathway_enrichment":
            return self._analyze_pathway_enrichment(data, params)
        else:
            return AnalysisResult(
                analysis_type=analysis_type,
                status="failed",
                data={},
                errors=[f"Unknown analysis type: {analysis_type}"],
            )
    
    def _analyze_differential_abundance(self, data: OmicsData, params: AnalysisParams) -> AnalysisResult:
        """Analyze differential protein abundance."""
        fdr_threshold = params.get("fdr_threshold", 0.05)
        log2fc_threshold = params.get("log2fc_threshold", 1.0)
        
        # Similar to transcriptomics DE analysis
        results = []
        
        if data.sample_metadata is not None and "condition" in data.sample_metadata.columns:
            conditions = data.sample_metadata["condition"].unique()
            if len(conditions) >= 2:
                group1 = data.sample_metadata[data.sample_metadata["condition"] == conditions[0]].index
                group2 = data.sample_metadata[data.sample_metadata["condition"] == conditions[1]].index
                
                for protein in data.feature_names:
                    if protein in data.data.columns:
                        g1_vals = data.data.loc[group1, protein].dropna()
                        g2_vals = data.data.loc[group2, protein].dropna()
                        
                        if len(g1_vals) > 1 and len(g2_vals) > 1:
                            mean1, mean2 = g1_vals.mean(), g2_vals.mean()
                            log2fc = np.log2((mean2 + 1) / (mean1 + 1))
                            t_stat, p_value = stats.ttest_ind(g1_vals, g2_vals)
                            
                            results.append({
                                "protein": protein,
                                "log2FoldChange": log2fc,
                                "pvalue": p_value,
                                "mean_group1": mean1,
                                "mean_group2": mean2,
                            })
        
        if results:
            da_df = pd.DataFrame(results)
            # FDR correction
            from scipy.stats import false_discovery_control
            da_df["padj"] = false_discovery_control(da_df["pvalue"].values, method="bh")
            da_df["significant"] = (da_df["padj"] < fdr_threshold) & (abs(da_df["log2FoldChange"]) > log2fc_threshold)
        else:
            da_df = pd.DataFrame()
        
        return AnalysisResult(
            analysis_type="differential_abundance",
            status="success",
            data={"da_results": da_df.to_dict("records") if not da_df.empty else []},
            summary={
                "n_proteins_tested": len(results),
                "n_significant": int(da_df["significant"].sum()) if not da_df.empty else 0,
            },
        )
    
    def _analyze_correlation(self, data: OmicsData, params: AnalysisParams) -> AnalysisResult:
        """Analyze protein correlations."""
        method = params.get("method", "pearson")
        threshold = params.get("threshold", 0.7)
        
        # Calculate correlation matrix
        corr_matrix = data.data.corr(method=method)
        
        # Find highly correlated pairs
        pairs = []
        for i, p1 in enumerate(data.feature_names):
            for j, p2 in enumerate(data.feature_names):
                if i < j and p1 in corr_matrix.columns and p2 in corr_matrix.columns:
                    corr = corr_matrix.loc[p1, p2]
                    if abs(corr) >= threshold:
                        pairs.append({"protein1": p1, "protein2": p2, "correlation": corr})
        
        return AnalysisResult(
            analysis_type="protein_correlation",
            status="success",
            data={"correlated_pairs": pairs},
            summary={"n_pairs": len(pairs), "threshold": threshold},
        )
    
    def _analyze_pathway_enrichment(self, data: OmicsData, params: AnalysisParams) -> AnalysisResult:
        """Over-representation analysis on high-variance proteins against curated sets."""
        from backend.omics._pathway_reference import hypergeom_enrichment, pathway_sets_for_entity

        top_n = int(params.get("top_n_features", 40))
        df = data.data.copy()
        if df.empty:
            return AnalysisResult(
                analysis_type="pathway_enrichment",
                status="success",
                data={"enriched_pathways": []},
                summary={"n_pathways_tested": 0},
            )

        var = df.var(axis=0)
        top = var.nlargest(min(top_n, len(var))).index.tolist()
        query = set(str(x) for x in top)
        background = set(str(x) for x in data.feature_names)
        sets = pathway_sets_for_entity("protein")
        enriched = hypergeom_enrichment(query, background, sets, max_p=1.0)

        return AnalysisResult(
            analysis_type="pathway_enrichment",
            status="success",
            data={"enriched_pathways": enriched, "query_features": list(query)},
            summary={"n_pathways_tested": len(sets), "n_significant": len(enriched)},
        )
    
    def visualize(
        self,
        result: AnalysisResult,
        plot_types: Optional[List[str]] = None,
    ) -> List[Visualization]:
        """Generate proteomics visualizations."""
        visualizations = []
        
        if result.analysis_type == "differential_abundance":
            if "da_results" in result.data and result.data["da_results"]:
                visualizations.append(Visualization(
                    name="volcano_plot",
                    plot_type="scatter",
                    data={
                        "x": [r["log2FoldChange"] for r in result.data["da_results"]],
                        "y": [-np.log10(r["pvalue"]) for r in result.data["da_results"]],
                        "text": [r["protein"] for r in result.data["da_results"]],
                    },
                    title="Protein Abundance Volcano Plot",
                ))
        
        return visualizations
    
    def get_available_pipelines(self) -> List[Pipeline]:
        return self._pipelines
    
    def get_available_analyses(self) -> List[AnalysisDefinition]:
        return self._analyses

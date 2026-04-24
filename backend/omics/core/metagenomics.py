"""
Metagenomics Module
===================

Environmental and microbiome genomics including:
- Taxonomic profiling
- Functional analysis
- Community composition
- Diversity analysis
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


class MetagenomicsModule(OmicsModuleBase):
    """Metagenomics analysis module for microbiome and environmental samples."""
    
    def __init__(self):
        super().__init__()
        self._version = "1.0.0"
        self._supported_formats = ["csv", "tsv", "biom", "qza"]
        
        self._pipelines = [
            Pipeline(
                name="16s_analysis",
                description="16S rRNA amplicon analysis pipeline",
                steps=["load_data", "quality_control", "taxonomic_assignment", "diversity_analysis", "differential_abundance"],
                default_parameters={"classifier": "silva", "rarefaction_depth": 10000},
            ),
            Pipeline(
                name="shotgun_metagenomics",
                description="Shotgun metagenomics analysis",
                steps=["load_data", "quality_control", "taxonomic_profiling", "functional_profiling", "pathway_analysis"],
                default_parameters={"profiler": "metaphlan", "functional_db": "humann"},
            ),
        ]
        
        self._analyses = [
            AnalysisDefinition(
                name="alpha_diversity",
                description="Calculate alpha diversity metrics",
                parameters={
                    "metrics": {"type": "list", "default": ["shannon", "simpson", "chao1"], "description": "Diversity metrics"},
                },
                output_types=["table", "boxplot"],
            ),
            AnalysisDefinition(
                name="beta_diversity",
                description="Calculate beta diversity and ordination",
                parameters={
                    "metric": {"type": "str", "default": "bray_curtis", "description": "Distance metric"},
                    "method": {"type": "str", "default": "pcoa", "description": "Ordination method"},
                },
                output_types=["distance_matrix", "ordination_plot"],
            ),
            AnalysisDefinition(
                name="differential_abundance",
                description="Differential abundance analysis",
                parameters={
                    "method": {"type": "str", "default": "ancom", "description": "DA method"},
                    "group_column": {"type": "str", "default": "condition", "description": "Grouping variable"},
                },
                output_types=["table", "volcano_plot"],
            ),
        ]
    
    @property
    def name(self) -> str:
        return "metagenomics"
    
    @property
    def category(self) -> OmicsCategory:
        return OmicsCategory.CORE
    
    @property
    def description(self) -> str:
        return "Microbiome and environmental genomics analysis"
    
    def load_data(self, source: DataSource) -> OmicsData:
        """Load metagenomics abundance data."""
        if source.source_type == "file":
            file_path = Path(source.path)
            format_type = source.format or file_path.suffix.lstrip(".")
            
            if format_type in ["csv", "tsv"]:
                sep = "\t" if format_type == "tsv" else ","
                df = pd.read_csv(file_path, sep=sep, index_col=0)
                return OmicsData(
                    data=df.T,
                    feature_names=df.index.tolist(),  # Taxa
                    sample_names=df.columns.tolist(),
                    data_type="metagenomics",
                    source=source,
                )
        raise ValueError(f"Unsupported source: {source.source_type}")
    
    def preprocess(self, data: OmicsData, params: Optional[Dict[str, Any]] = None) -> OmicsData:
        """Preprocess metagenomics data."""
        params = params or {}
        processed = data.copy()
        
        # Filter low abundance taxa
        min_prevalence = params.get("min_prevalence", 0.1)
        min_abundance = params.get("min_abundance", 0.001)
        
        # Prevalence filter
        prevalence = (processed.data > 0).sum(axis=0) / len(processed.sample_names)
        keep = prevalence >= min_prevalence
        processed.data = processed.data.loc[:, keep]
        processed.feature_names = [f for f, k in zip(processed.feature_names, keep) if k]
        
        processed.preprocessing_history.append(f"preprocess(min_prevalence={min_prevalence})")
        return processed
    
    def quality_control(self, data: OmicsData, params: Optional[Dict[str, Any]] = None) -> QCReport:
        """QC for metagenomics data."""
        metrics = []
        
        n_taxa = len(data.feature_names)
        metrics.append(QCMetric(name="taxa_count", value=n_taxa, threshold=10))
        
        # Read depth
        read_depths = data.data.sum(axis=1)
        min_depth = read_depths.min()
        metrics.append(QCMetric(name="min_read_depth", value=min_depth, threshold=1000))
        
        passed = all(m.passed for m in metrics if m.passed is not None)
        return QCReport(passed=passed, metrics=metrics, details={"median_depth": float(read_depths.median())})
    
    def normalize(self, data: OmicsData, method: str = "relative", params: Optional[Dict[str, Any]] = None) -> OmicsData:
        """Normalize metagenomics data."""
        normalized = data.copy()
        
        if method == "relative":
            normalized.data = normalized.data.div(normalized.data.sum(axis=1), axis=0)
        elif method == "clr":  # Centered log-ratio
            geom_mean = np.exp(np.log(normalized.data + 1).mean(axis=1))
            normalized.data = np.log((normalized.data + 1).div(geom_mean, axis=0))
        elif method == "rarefaction":
            depth = params.get("depth", int(normalized.data.sum(axis=1).min()))
            # Simplified rarefaction
            normalized.data = normalized.data.div(normalized.data.sum(axis=1), axis=0) * depth
        
        normalized.preprocessing_history.append(f"normalize(method={method})")
        return normalized
    
    def analyze(self, data: OmicsData, params: AnalysisParams) -> AnalysisResult:
        """Run metagenomics analysis."""
        if params.analysis_type == "alpha_diversity":
            return self._analyze_alpha_diversity(data, params)
        elif params.analysis_type == "beta_diversity":
            return self._analyze_beta_diversity(data, params)
        elif params.analysis_type == "differential_abundance":
            return self._analyze_differential(data, params)
        return AnalysisResult(analysis_type=params.analysis_type, status="failed", data={}, errors=["Unknown analysis"])
    
    def _analyze_alpha_diversity(self, data: OmicsData, params: AnalysisParams) -> AnalysisResult:
        """Calculate alpha diversity metrics."""
        results = []
        
        for sample in data.sample_names:
            if sample in data.data.index:
                abundances = data.data.loc[sample].values
                abundances = abundances[abundances > 0]
                
                if len(abundances) > 0:
                    # Shannon diversity
                    props = abundances / abundances.sum()
                    shannon = -np.sum(props * np.log(props))
                    
                    # Observed species
                    observed = len(abundances)
                    
                    # Simpson index
                    simpson = 1 - np.sum(props ** 2)
                    
                    results.append({
                        "sample": sample,
                        "shannon": shannon,
                        "observed": observed,
                        "simpson": simpson,
                    })
        
        return AnalysisResult(
            analysis_type="alpha_diversity",
            status="success",
            data={"diversity_metrics": results},
            summary={"n_samples": len(results)},
        )
    
    def _analyze_beta_diversity(self, data: OmicsData, params: AnalysisParams) -> AnalysisResult:
        """Calculate beta diversity."""
        from scipy.spatial.distance import pdist, squareform
        
        metric = params.get("metric", "braycurtis")
        
        # Calculate distance matrix
        distances = pdist(data.data.values, metric=metric)
        dist_matrix = squareform(distances)
        
        dist_df = pd.DataFrame(
            dist_matrix,
            index=data.sample_names,
            columns=data.sample_names
        )
        
        return AnalysisResult(
            analysis_type="beta_diversity",
            status="success",
            data={"distance_matrix": dist_df.to_dict()},
            summary={"metric": metric, "n_samples": len(data.sample_names)},
        )
    
    def _analyze_differential(self, data: OmicsData, params: AnalysisParams) -> AnalysisResult:
        """Differential abundance analysis."""
        results = []
        
        if data.sample_metadata is not None and "condition" in data.sample_metadata.columns:
            conditions = data.sample_metadata["condition"].unique()
            if len(conditions) >= 2:
                g1 = data.sample_metadata[data.sample_metadata["condition"] == conditions[0]].index
                g2 = data.sample_metadata[data.sample_metadata["condition"] == conditions[1]].index
                
                for taxon in data.feature_names:
                    if taxon in data.data.columns:
                        v1, v2 = data.data.loc[g1, taxon].dropna(), data.data.loc[g2, taxon].dropna()
                        if len(v1) > 1 and len(v2) > 1:
                            # Mann-Whitney U test (non-parametric)
                            u, p = stats.mannwhitneyu(v1, v2, alternative='two-sided')
                            fc = np.log2((v2.mean() + 1e-10) / (v1.mean() + 1e-10))
                            results.append({"taxon": taxon, "log2FC": fc, "pvalue": p})
        
        return AnalysisResult(
            analysis_type="differential_abundance",
            status="success",
            data={"da_results": results},
            summary={"n_taxa_tested": len(results)},
        )
    
    def visualize(self, result: AnalysisResult, plot_types: Optional[List[str]] = None) -> List[Visualization]:
        return []
    
    def get_available_pipelines(self) -> List[Pipeline]:
        return self._pipelines
    
    def get_available_analyses(self) -> List[AnalysisDefinition]:
        return self._analyses

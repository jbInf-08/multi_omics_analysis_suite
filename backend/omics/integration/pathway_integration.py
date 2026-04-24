"""Pathway-Based Multi-Omics Integration."""

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from backend.omics.base.omics_base import OmicsData


@dataclass
class PathwayResult:
    """Pathway integration result."""

    pathway_scores: pd.DataFrame
    enriched_pathways: list[dict]
    pathway_genes: dict[str, list[str]]
    method: str
    metadata: dict[str, Any]


class PathwayIntegrator:
    """Pathway-based integration of multi-omics data.

    Aggregates features within pathways for cross-omics analysis.
    """

    def __init__(
        self,
        database: str = "kegg",
        organism: str = "hsa",
    ):
        """Initialize pathway integrator.

        Args:
            database: Pathway database ('kegg', 'reactome', 'go')
            organism: Organism code

        """
        self.database = database
        self.organism = organism
        self.pathways: dict[str, set[str]] = {}

    def load_pathways(self, pathway_file: str | None = None) -> "PathwayIntegrator":
        """Load pathway definitions.

        Args:
            pathway_file: Path to pathway GMT file (optional)

        """
        if pathway_file:
            self._load_gmt(pathway_file)
        else:
            self._load_default_pathways()
        return self

    def _load_gmt(self, filepath: str):
        """Load pathways from GMT file."""
        with open(filepath) as f:
            for line in f:
                parts = line.strip().split("\t")
                if len(parts) >= 3:
                    pathway_name = parts[0]
                    genes = set(parts[2:])
                    self.pathways[pathway_name] = genes

    def _load_default_pathways(self):
        """Load default example pathways."""
        # Simplified example pathways
        self.pathways = {
            "Cell_Cycle": {"CDKN1A", "CDKN1B", "CDK4", "CDK6", "CCND1", "CCNE1", "RB1", "E2F1"},
            "Apoptosis": {"BCL2", "BAX", "CASP3", "CASP8", "CASP9", "TP53", "PARP1"},
            "DNA_Repair": {"BRCA1", "BRCA2", "ATM", "ATR", "CHEK1", "CHEK2", "RAD51"},
            "PI3K_AKT": {"PIK3CA", "AKT1", "PTEN", "MTOR", "TSC1", "TSC2"},
            "MAPK": {"KRAS", "BRAF", "MAP2K1", "MAPK1", "MAPK3", "ERK1", "ERK2"},
            "WNT": {"WNT1", "CTNNB1", "APC", "GSK3B", "AXIN1"},
            "TGF_Beta": {"TGFB1", "SMAD2", "SMAD3", "SMAD4", "SMAD7"},
            "Immune_Response": {"CD8A", "CD4", "IFNG", "TNF", "IL2", "IL6", "IL10"},
        }

    def compute_pathway_scores(
        self,
        datasets: dict[str, OmicsData],
        method: str = "mean",
    ) -> PathwayResult:
        """Compute pathway-level scores for each omics.

        Args:
            datasets: Dict of omics datasets
            method: Aggregation method ('mean', 'median', 'pca', 'gsva')

        Returns:
            PathwayResult with pathway scores

        """
        # Align samples
        aligned = self._align_samples(datasets)
        sample_names = list(aligned.values())[0].index.tolist()

        # Compute scores for each omics type
        all_scores = {}

        for omics_name, df in aligned.items():
            omics_scores = {}

            for pathway_name, pathway_genes in self.pathways.items():
                # Find overlapping genes
                available_genes = [g for g in pathway_genes if g in df.columns]

                if len(available_genes) >= 2:
                    pathway_data = df[available_genes].values

                    if method == "mean":
                        scores = np.nanmean(pathway_data, axis=1)
                    elif method == "median":
                        scores = np.nanmedian(pathway_data, axis=1)
                    elif method == "pca":
                        from sklearn.decomposition import PCA

                        pca = PCA(n_components=1)
                        scores = pca.fit_transform(pathway_data).flatten()
                    else:
                        scores = np.nanmean(pathway_data, axis=1)

                    omics_scores[f"{omics_name}_{pathway_name}"] = scores

            all_scores.update(omics_scores)

        # Create DataFrame
        scores_df = pd.DataFrame(all_scores, index=sample_names)

        return PathwayResult(
            pathway_scores=scores_df,
            enriched_pathways=[],
            pathway_genes={k: list(v) for k, v in self.pathways.items()},
            method=method,
            metadata={
                "n_pathways": len(self.pathways),
                "n_omics": len(datasets),
                "database": self.database,
            },
        )

    def pathway_enrichment(
        self,
        gene_scores: dict[str, float],
        method: str = "gsea",
        n_permutations: int = 1000,
    ) -> list[dict]:
        """Perform pathway enrichment analysis.

        Args:
            gene_scores: Dict mapping gene to score (e.g., log2FC)
            method: Enrichment method ('gsea', 'ora')
            n_permutations: Number of permutations for GSEA

        Returns:
            List of enriched pathways with statistics

        """
        results = []

        for pathway_name, pathway_genes in self.pathways.items():
            # Get scores for pathway genes
            pathway_scores = [gene_scores.get(g, 0) for g in pathway_genes if g in gene_scores]
            background_scores = [s for g, s in gene_scores.items() if g not in pathway_genes]

            if len(pathway_scores) >= 2 and len(background_scores) >= 2:
                if method == "gsea":
                    # Simplified GSEA-like test
                    es, p_value = self._compute_enrichment_score(
                        pathway_scores, background_scores, n_permutations
                    )
                else:
                    # Over-representation analysis
                    t_stat, p_value = stats.ttest_ind(pathway_scores, background_scores)
                    es = np.mean(pathway_scores) - np.mean(background_scores)

                results.append(
                    {
                        "pathway": pathway_name,
                        "enrichment_score": es,
                        "p_value": p_value,
                        "n_genes": len(pathway_scores),
                        "genes": [g for g in pathway_genes if g in gene_scores],
                    }
                )

        # Sort by p-value
        results.sort(key=lambda x: x["p_value"])

        # FDR correction
        p_values = [r["p_value"] for r in results]
        if p_values:
            from scipy.stats import false_discovery_control

            q_values = false_discovery_control(p_values, method="bh")
            for i, r in enumerate(results):
                r["q_value"] = q_values[i]

        return results

    def _compute_enrichment_score(
        self,
        pathway_scores: list[float],
        background_scores: list[float],
        n_permutations: int,
    ) -> tuple:
        """Compute enrichment score with permutation test."""
        # Observed difference
        observed_diff = np.mean(pathway_scores) - np.mean(background_scores)

        # Permutation test
        all_scores = pathway_scores + background_scores
        n_pathway = len(pathway_scores)

        null_diffs = []
        for _ in range(n_permutations):
            perm = np.random.permutation(all_scores)
            perm_diff = np.mean(perm[:n_pathway]) - np.mean(perm[n_pathway:])
            null_diffs.append(perm_diff)

        # P-value
        if observed_diff >= 0:
            p_value = (np.sum(null_diffs >= observed_diff) + 1) / (n_permutations + 1)
        else:
            p_value = (np.sum(null_diffs <= observed_diff) + 1) / (n_permutations + 1)

        return observed_diff, p_value

    def _align_samples(self, datasets: dict[str, OmicsData]) -> dict[str, pd.DataFrame]:
        """Align samples across datasets."""
        common_samples = None
        for name, data in datasets.items():
            samples = set(data.sample_names)
            if common_samples is None:
                common_samples = samples
            else:
                common_samples = common_samples.intersection(samples)

        common_samples = sorted(common_samples)

        aligned = {}
        for name, data in datasets.items():
            df = data.data.copy()
            if not isinstance(df.index, pd.Index) or list(df.index) != data.sample_names:
                df.index = data.sample_names
            aligned[name] = df.loc[common_samples]

        return aligned

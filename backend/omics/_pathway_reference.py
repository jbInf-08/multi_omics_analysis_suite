"""Small curated gene/protein sets for ORA / preranked enrichment (no external DB required)."""

from __future__ import annotations

from typing import Dict, List, Set

PATHWAY_GENE_SETS: Dict[str, List[str]] = {
    "Cell_cycle": ["CDK1", "CCNB1", "CCNA2", "CDC20", "PLK1", "TOP2A", "MKI67", "PCNA"],
    "Immune_response": ["CD3E", "CD8A", "CD4", "CD19", "MS4A1", "CD14", "FCGR3A", "IL2RA"],
    "Apoptosis": ["CASP3", "CASP8", "BAX", "BCL2", "FAS", "TNF", "CYCS", "DIABLO"],
    "Metabolism": ["HK2", "PFKM", "PKM", "LDHA", "IDH1", "CS", "MDH2", "ACO2"],
    "DNA_repair": ["BRCA1", "BRCA2", "RAD51", "PARP1", "ATM", "ATR", "MLH1", "MSH2"],
}

PATHWAY_PROTEIN_SETS: Dict[str, List[str]] = {k: list(v) for k, v in PATHWAY_GENE_SETS.items()}


def pathway_sets_for_entity(entity: str) -> Dict[str, List[str]]:
    entity = (entity or "gene").lower()
    if entity in ("protein", "proteomics"):
        return PATHWAY_PROTEIN_SETS
    return PATHWAY_GENE_SETS


def hypergeom_enrichment(
    query: Set[str],
    background: Set[str],
    gene_sets: Dict[str, List[str]],
    max_p: float = 1.0,
) -> List[Dict[str, float]]:
    """Fisher exact test (greater) for over-representation in a fixed background."""
    from scipy.stats import fisher_exact

    if not query or not background:
        return []

    U = background
    Q = query & U
    if not Q:
        return []

    results: List[Dict[str, float]] = []
    for pathway, genes in gene_sets.items():
        P = set(genes) & U
        if len(P) < 2:
            continue
        a = len(Q & P)
        b = len(Q - P)
        c = len(P - Q)
        d = len(U) - len(Q) - len(P) + a
        if min(a, b, c, d) < 0:
            continue
        _, pvalue = fisher_exact([[a, b], [c, d]], alternative="greater")
        if pvalue <= max_p:
            results.append(
                {
                    "pathway": pathway,
                    "overlap": float(a),
                    "pathway_size": float(len(P)),
                    "query_size": float(len(Q)),
                    "pvalue": float(pvalue),
                }
            )

    results.sort(key=lambda r: r["pvalue"])
    return results


def preranked_gsea_like(
    ranked_genes: List[str],
    gene_ranks: List[float],
    gene_sets: Dict[str, List[str]],
    n_perm: int = 200,
    seed: int = 42,
) -> List[Dict[str, float]]:
    """
    Rank-based enrichment: score = mean(rank in set) - mean(global rank), with permutation p.
    """
    import numpy as np

    if not ranked_genes or not gene_ranks or len(ranked_genes) != len(gene_ranks):
        return []

    rng = np.random.default_rng(seed)
    genes = np.array(ranked_genes)
    scores = np.asarray(gene_ranks, dtype=float)
    n = len(genes)

    def mean_rank_diff(gset: Set[str]) -> float:
        idx = np.array([i for i, g in enumerate(genes) if g in gset], dtype=int)
        if idx.size == 0:
            return 0.0
        order = np.argsort(-scores)
        ranks = np.empty(n, dtype=float)
        ranks[order] = np.arange(1, n + 1, dtype=float)
        in_set = ranks[idx]
        return float(in_set.mean() - ranks.mean())

    obs: Dict[str, float] = {}
    for name, lst in gene_sets.items():
        obs[name] = mean_rank_diff(set(lst))

    counts = {k: 0 for k in obs}
    for _ in range(n_perm):
        perm = rng.permutation(scores)
        order = np.argsort(-perm)
        ranks = np.empty(n, dtype=float)
        ranks[order] = np.arange(1, n + 1, dtype=float)
        glob_mean = ranks.mean()
        for name, lst in gene_sets.items():
            idx = np.array([i for i, g in enumerate(genes) if g in set(lst)], dtype=int)
            if idx.size == 0:
                continue
            sp = float(ranks[idx].mean() - glob_mean)
            if abs(sp) >= abs(obs.get(name, 0.0)):
                counts[name] += 1

    out: List[Dict[str, float]] = []
    for name, sc in obs.items():
        p = (counts[name] + 1) / (n_perm + 1)
        out.append({"pathway": name, "enrichment_score": float(sc), "pvalue": float(p)})
    out.sort(key=lambda r: r["pvalue"])
    return out

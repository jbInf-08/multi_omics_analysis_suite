"""
Pathway-level helpers for systems biology (curated sets + visualization hooks).

For large-scale KEGG/Reactome queries, integrate external services or
``backend.analysis.pathway_analysis`` as needed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

try:
    from backend.omics._pathway_reference import (
        PATHWAY_GENE_SETS,
        hypergeom_enrichment,
        pathway_sets_for_entity,
    )
except ImportError:  # pragma: no cover
    PATHWAY_GENE_SETS = {}

    def pathway_sets_for_entity(entity: str) -> Dict[str, List[str]]:  # noqa: ARG001
        return {}

    hypergeom_enrichment = None


class PathwayDatabase(str, Enum):
    """Logical pathway source (curated in-repo sets vs external DB identifiers)."""

    CURATED = "curated"
    KEGG = "kegg"
    REACTOME = "reactome"
    WIKIPATHWAYS = "wikipathways"


@dataclass(frozen=True)
class Pathway:
    """A named set of genes/proteins."""

    pathway_id: str
    name: str
    members: frozenset[str] = field(default_factory=frozenset)

    @classmethod
    def from_curated_key(cls, key: str) -> "Pathway":
        genes = PATHWAY_GENE_SETS.get(key, [])
        return cls(pathway_id=key, name=key.replace("_", " "), members=frozenset(genes))


class PathwayEnrichment:
    """Over-representation-style enrichment against bundled gene sets."""

    def __init__(self, database: PathwayDatabase = PathwayDatabase.CURATED):
        self.database = database

    def enrich(
        self,
        query_genes: Iterable[str],
        universe: Optional[Set[str]] = None,
        entity: str = "gene",
        max_p: float = 0.05,
    ) -> List[Dict[str, Any]]:
        if hypergeom_enrichment is None:
            return []

        q = {g.upper() for g in query_genes if g}
        if not q:
            return []

        gene_sets = pathway_sets_for_entity(entity)
        if self.database != PathwayDatabase.CURATED:
            # External DBs are identifiers only here; fall back to curated sets.
            gene_sets = pathway_sets_for_entity(entity)

        if universe is None:
            universe = set().union(*gene_sets.values()) | q
        else:
            universe = {g.upper() for g in universe}

        return hypergeom_enrichment(q, universe, gene_sets, max_p=max_p)


class PathwayVisualization:
    """Cytoscape.js-compatible graph payloads for small pathways."""

    @staticmethod
    def cytoscape_elements(
        pathway: Pathway,
        edges: Optional[List[Tuple[str, str]]] = None,
    ) -> Dict[str, List[Dict[str, Any]]]:
        nodes = [{"data": {"id": m, "label": m}} for m in sorted(pathway.members)]
        el_edges: List[Dict[str, Any]] = []
        for i, (a, b) in enumerate(edges or []):
            if a in pathway.members and b in pathway.members:
                el_edges.append({"data": {"id": f"e{i}", "source": a, "target": b}})
        return {"nodes": nodes, "edges": el_edges}


class MetabolicFluxAnalysis:
    """
    Minimal flux-balance scaffold: maximize (or set) a linear objective
    subject to ``S v = 0``, ``v >= 0``.

    Full genome-scale models are better handled with COBRApy; this stays
    dependency-light with SciPy ``linprog`` when available.
    """

    def __init__(self, stoichiometry: Any, flux_bounds: Optional[List[Tuple[float, float]]] = None):
        import numpy as np

        self.S = np.asarray(stoichiometry, dtype=float)
        self.flux_bounds = flux_bounds

    def flux_balance(
        self,
        objective: Optional[Any] = None,
        maximize: bool = True,
    ) -> Dict[str, Any]:
        import numpy as np

        try:
            from scipy.optimize import linprog
        except ImportError:
            return {
                "success": False,
                "status": "scipy_required",
                "message": "Install scipy for flux_balance LP.",
                "fluxes": None,
            }

        S = self.S
        if S.ndim != 2:
            return {"success": False, "status": "bad_shape", "fluxes": None}
        m, n = S.shape
        if objective is None:
            c = np.zeros(n)
            c[0] = 1.0
        else:
            c = np.asarray(objective, dtype=float).reshape(-1)
            if c.size != n:
                return {"success": False, "status": "objective_length", "fluxes": None}
        if maximize:
            c = -c

        if self.flux_bounds is None:
            bounds: List[Tuple[Optional[float], Optional[float]]] = [(0.0, None)] * n
        else:
            if len(self.flux_bounds) != n:
                return {"success": False, "status": "bounds_length", "fluxes": None}
            bounds = list(self.flux_bounds)

        res = linprog(
            c,
            A_eq=S,
            b_eq=np.zeros(m),
            bounds=bounds,
            method="highs",
        )
        fluxes = (-res.fun,) if maximize and res.success else (res.fun,)
        return {
            "success": bool(res.success),
            "status": res.message,
            "fluxes": res.x.tolist() if res.success else None,
            "objective_value": float(fluxes[0]) if res.success else None,
        }

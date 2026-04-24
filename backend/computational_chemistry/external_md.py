"""
Optional external MD engines (OpenMM, GROMACS).

The default stack uses ``molecular_dynamics.MDSimulation``. For production trajectories,
wire an implementation of :class:`ExternalMDEngine` that shells out to GROMACS or uses OpenMM,
then feed resulting coordinates into ``TrajectoryAnalyzer`` or the structure–MD–dock pipeline.

When no engine is registered, :func:`external_md_not_configured` returns a dict with
``configured=False`` and an ``error`` message instead of raising.

**OpenMM**: add ``openmm`` to dependencies, build ``openmm.app.Topology`` from PDB, assign a
force field XML, run ``Simulation``, export positions per frame.

**GROMACS**: write coordinates/topology from PDB, run ``gmx grompp`` / ``gmx mdrun``, read
``.xtc`` with MDAnalysis (already a project dependency).
"""

from __future__ import annotations

from typing import Any, Dict, Protocol


class ExternalMDEngine(Protocol):
    """Protocol for swapping the bundled MD engine."""

    def run(
        self,
        pdb_path: str,
        output_prefix: str,
        n_steps: int,
        temperature_k: float,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Run MD; return paths to trajectory/energy files and summary metrics."""
        ...


def external_md_not_configured(*_args: Any, **_kwargs: Any) -> Dict[str, Any]:
    """
    Return a structured response when an external engine is requested but not wired.

    Callers should check ``configured`` (False) instead of catching :class:`NotImplementedError`.
    """
    return {
        "configured": False,
        "error": (
            "External MD engine not configured. See external_md.py module docstring "
            "for OpenMM/GROMACS integration."
        ),
        "trajectory_path": None,
        "energy_path": None,
        "metrics": {},
    }

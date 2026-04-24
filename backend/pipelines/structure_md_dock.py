"""Structure → molecular dynamics → molecular docking pipeline.

Uses a geometric binding site at the receptor center when cavity detection returns none,
so docking remains usable with the bundled scoring engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from backend.computational_chemistry.docking import (
    BindingSite,
    MolecularDocking,
    binding_site_at_receptor_center,
)
from backend.computational_chemistry.molecular_dynamics import (
    BerendsenThermostat,
    MDSimulation,
    TrajectoryAnalyzer,
)
from backend.computational_chemistry.structure import Molecule


@dataclass
class StructureMDDockPipeline:
    """Configurable structure / MD / docking run."""

    md_steps: int = 200
    md_save_interval: int = 50
    md_box_size: float = 80.0
    md_temperature: float = 300.0
    minimize_steps: int = 50
    docking_poses: int = 10
    docking_exhaustiveness: int = 4

    def run(
        self,
        protein: Molecule,
        ligand: Molecule,
        binding_site: BindingSite | None = None,
    ) -> dict[str, Any]:
        protein = self._copy_molecule(protein, name=protein.name or "receptor")
        ligand = self._copy_molecule(ligand, name=ligand.name or "ligand")

        md = MDSimulation(
            protein,
            thermostat=BerendsenThermostat(self.md_temperature, tau=0.5),
        )
        md.initialize(box_size=self.md_box_size, temperature=self.md_temperature)
        md.minimize_energy(max_steps=self.minimize_steps, tolerance=0.5)
        md.run(
            n_steps=self.md_steps,
            save_interval=self.md_save_interval,
            print_interval=self.md_steps + 1,
        )

        protein.positions = md.state.positions.copy()

        analyzer = TrajectoryAnalyzer(md.trajectory)
        ref = md.trajectory[0].positions if md.trajectory else protein.positions.copy()
        rmsd = analyzer.calculate_rmsd(ref) if md.trajectory else np.array([])
        rg = analyzer.calculate_radius_of_gyration() if md.trajectory else np.array([])
        energy_stats = analyzer.energy_statistics() if md.trajectory else {}

        site = binding_site or binding_site_at_receptor_center(protein)
        dock = MolecularDocking(
            exhaustiveness=self.docking_exhaustiveness,
            n_poses=self.docking_poses,
        )
        poses = dock.dock(ligand, protein, binding_site=site)

        return {
            "md": {
                "n_steps": self.md_steps,
                "n_frames": len(md.trajectory),
                "final_total_energy_kcal_mol": float(md.state.total_energy) if md.state else None,
                "final_temperature_K": float(md.state.temperature) if md.state else None,
                "rmsd_trajectory": rmsd.tolist(),
                "radius_of_gyration": rg.tolist(),
                "energy_statistics": energy_stats,
            },
            "docking": {
                "n_poses_returned": len(poses),
                "poses": [
                    {
                        "rank": p.rank,
                        "total_score": float(p.score.total_score),
                        "vdw": float(p.score.van_der_waals),
                        "electrostatic": float(p.score.electrostatic),
                        "n_contacts": len(p.contacts),
                    }
                    for p in poses
                ],
            },
        }

    @staticmethod
    def _copy_molecule(mol: Molecule, name: str) -> Molecule:
        """Reload coordinates from serialized PDB to avoid accidental shared state."""
        clone = Molecule.from_pdb(mol.to_pdb())
        clone.name = name
        return clone


def run_structure_md_dock(
    protein_pdb: str,
    ligand_pdb: str,
    binding_site: BindingSite | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Run the full pipeline from PDB text.

    Pipeline tuning kwargs (e.g. ``md_steps``) are forwarded to :class:`StructureMDDockPipeline`.
    """
    protein = Molecule.from_pdb(protein_pdb)
    ligand = Molecule.from_pdb(ligand_pdb)
    field_names = set(StructureMDDockPipeline.__dataclass_fields__)
    cfg = StructureMDDockPipeline(**{k: v for k, v in kwargs.items() if k in field_names})
    return cfg.run(protein, ligand, binding_site=binding_site)

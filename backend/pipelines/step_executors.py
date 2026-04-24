"""
Dispatchers for Celery pipeline steps (gene annotation, structure–MD–docking).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from backend.assembly.assemblers import AssemblyResult, Contig
from backend.pipelines.gene_annotation import annotate_assembly_result, annotate_fasta_path
from backend.pipelines.structure_md_dock import run_structure_md_dock


def _read_text(path: str) -> str:
    return Path(path).read_text(encoding="utf-8", errors="replace")


def execute_step(
    step: Dict[str, Any],
    _prior_results: List[Dict[str, Any]],
    run_parameters: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Run a single pipeline step. ``_prior_results`` may be used later for step chaining.
    """
    merged = {**run_parameters, **(step.get("params") or {})}
    stype = (step.get("type") or step.get("name") or "").lower().strip()

    if stype in ("gene_prediction", "annotate_fasta", "fasta_gene_annotation"):
        fasta_path = merged.get("fasta_path") or merged.get("assembly_fasta_path")
        if not fasta_path:
            raise ValueError("gene_prediction step requires 'fasta_path' or 'assembly_fasta_path'")
        predictor = merged.get("predictor", "prodigal")
        gff_out = merged.get("gff_output_path")
        return annotate_fasta_path(
            fasta_path,
            predictor=predictor,
            include_sequences=bool(merged.get("include_sequences", False)),
            gff_output=gff_out,
            use_prodigal_binary=bool(merged.get("use_prodigal_binary", False)),
            prodigal_meta_mode=bool(merged.get("prodigal_meta_mode", False)),
        )

    if stype in ("assembly_gene_annotation", "assembly_annotation"):
        # Prefer explicit AssemblyResult JSON shape from a prior assembler step
        assembly_dict = merged.get("assembly_result")
        predictor = merged.get("predictor", "prodigal")
        if assembly_dict and "contigs" in assembly_dict:
            contigs = [
                Contig(
                    id=c["id"],
                    sequence=c["sequence"],
                    coverage=float(c.get("coverage", 0.0)),
                )
                for c in assembly_dict["contigs"]
            ]
            ar = AssemblyResult(contigs=contigs)
            return annotate_assembly_result(
                ar,
                predictor=predictor,
                include_sequences=bool(merged.get("include_sequences", False)),
                use_prodigal_binary=bool(merged.get("use_prodigal_binary", False)),
                prodigal_meta_mode=bool(merged.get("prodigal_meta_mode", False)),
            )
        fasta_path = merged.get("fasta_path") or merged.get("assembly_fasta_path")
        if not fasta_path:
            raise ValueError(
                "assembly_gene_annotation requires 'assembly_result' dict or 'assembly_fasta_path'",
            )
        return annotate_fasta_path(
            fasta_path,
            predictor=predictor,
            include_sequences=bool(merged.get("include_sequences", False)),
            gff_output=merged.get("gff_output_path"),
            use_prodigal_binary=bool(merged.get("use_prodigal_binary", False)),
            prodigal_meta_mode=bool(merged.get("prodigal_meta_mode", False)),
        )

    if stype in ("structure_md_dock", "md_dock", "structure_md_docking"):
        p_pdb = merged.get("protein_pdb")
        l_pdb = merged.get("ligand_pdb")
        if not p_pdb:
            pp = merged.get("protein_pdb_path")
            if pp:
                p_pdb = _read_text(pp)
        if not l_pdb:
            lp = merged.get("ligand_pdb_path")
            if lp:
                l_pdb = _read_text(lp)
        if not p_pdb or not l_pdb:
            raise ValueError(
                "structure_md_dock step requires protein_pdb/ligand_pdb text or *_pdb_path files",
            )
        md_steps = int(merged.get("md_steps", 200))
        md_save_interval = int(merged.get("md_save_interval", 50))
        md_box_size = float(merged.get("md_box_size", 80.0))
        md_temperature = float(merged.get("md_temperature", 300.0))
        minimize_steps = int(merged.get("minimize_steps", 50))
        docking_poses = int(merged.get("docking_poses", 10))
        docking_exhaustiveness = int(merged.get("docking_exhaustiveness", 4))
        return run_structure_md_dock(
            p_pdb,
            l_pdb,
            md_steps=md_steps,
            md_save_interval=md_save_interval,
            md_box_size=md_box_size,
            md_temperature=md_temperature,
            minimize_steps=minimize_steps,
            docking_poses=docking_poses,
            docking_exhaustiveness=docking_exhaustiveness,
        )

    raise ValueError(f"Unsupported pipeline step type: {stype!r}")

"""
REST endpoints for gene prediction, molecular dynamics, docking, and combined pipelines.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from backend.annotation.gene_prediction import GenePrediction
from backend.app.core.security import (
    TokenPayload,
    check_chemistry_tools_rate_limit,
    get_tools_authorization,
)
from backend.computational_chemistry.docking import binding_site_at_receptor_center
from backend.pipelines.gene_annotation import (
    annotate_assembly_result,
    annotate_fasta_path,
    predict_genes_for_contig,
)
from backend.pipelines.structure_md_dock import run_structure_md_dock

router = APIRouter()


class GenePredictRequest(BaseModel):
    """Predict genes on one contig."""

    sequence: str = Field(..., min_length=3, description="DNA sequence (one contig)")
    contig_id: str = Field("contig", min_length=1, max_length=256)
    predictor: str = Field("prodigal", description="prodigal|augustus|glimmer|metagene|orf")
    include_sequences: bool = False
    use_prodigal_binary: bool = Field(
        False,
        description="If true and predictor is prodigal, run the Prodigal executable on a temp FASTA",
    )
    prodigal_meta_mode: bool = False


class GenePredictFromFastaRequest(BaseModel):
    """Predict genes from multi-record FASTA content."""

    fasta: str = Field(..., min_length=4, description="FASTA file contents")
    predictor: str = Field("prodigal")
    include_sequences: bool = False
    max_genes: int = Field(500, ge=1, le=5000)
    use_prodigal_binary: bool = False
    prodigal_meta_mode: bool = False


class AssemblyGeneAnnotateRequest(BaseModel):
    """Gene prediction on assembled contigs."""

    contigs: List[Dict[str, Any]] = Field(
        ...,
        description="List of {id, sequence, coverage?} per contig",
    )
    predictor: str = Field("prodigal")
    include_sequences: bool = False
    use_prodigal_binary: bool = False
    prodigal_meta_mode: bool = False


class MDRunRequest(BaseModel):
    """Run short MD on a structure given as PDB text."""

    pdb: str = Field(..., min_length=10)
    n_steps: int = Field(100, ge=1, le=50_000)
    save_interval: int = Field(25, ge=1, le=10_000)
    box_size: float = Field(80.0, gt=0)
    temperature: float = Field(300.0, gt=0)
    minimize_steps: int = Field(30, ge=0, le=5000)


class DockingRunRequest(BaseModel):
    """Protein–ligand docking from PDB text."""

    protein_pdb: str = Field(..., min_length=10)
    ligand_pdb: str = Field(..., min_length=10)
    n_poses: int = Field(10, ge=1, le=100)
    exhaustiveness: int = Field(4, ge=1, le=32)


class StructureMDDockRequest(BaseModel):
    """Full structure relaxation (MD) then docking."""

    protein_pdb: str = Field(..., min_length=10)
    ligand_pdb: str = Field(..., min_length=10)
    md_steps: int = Field(150, ge=1, le=50_000)
    md_save_interval: int = Field(50, ge=1, le=10_000)
    md_box_size: float = Field(80.0, gt=0)
    md_temperature: float = Field(300.0, gt=0)
    minimize_steps: int = Field(40, ge=0, le=5000)
    docking_poses: int = Field(10, ge=1, le=100)
    docking_exhaustiveness: int = Field(4, ge=1, le=32)


@router.post("/annotation/genes/predict", tags=["Annotation"])
async def api_predict_genes_contig(
    body: GenePredictRequest,
    _auth: TokenPayload = Depends(get_tools_authorization),
):
    """Predict gene coordinates on a single DNA sequence."""
    import tempfile

    if body.use_prodigal_binary and body.predictor.lower() == "prodigal":
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".fa", delete=False, encoding="utf-8"
            ) as tmp:
                tmp.write(f">{body.contig_id}\n{body.sequence.strip()}\n")
                path = Path(tmp.name)
            try:
                result = annotate_fasta_path(
                    path,
                    predictor="prodigal",
                    include_sequences=body.include_sequences,
                    use_prodigal_binary=True,
                    prodigal_meta_mode=body.prodigal_meta_mode,
                )
            finally:
                path.unlink(missing_ok=True)
        except (ValueError, RuntimeError) as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
        return {
            "predictor": "prodigal",
            "prodigal_backend": "binary",
            "n_genes": result["total_genes"],
            "gff": result["gff"],
            "genes": result.get("genes") or [],
        }

    try:
        preds = predict_genes_for_contig(
            body.sequence,
            body.contig_id,
            body.predictor,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    def row(g: GenePrediction) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "id": g.id,
            "contig": g.contig,
            "start": g.start,
            "end": g.end,
            "strand": g.strand,
            "gene_type": g.gene_type,
            "score": g.score,
            "length": g.length,
        }
        if body.include_sequences:
            d["nucleotide_seq"] = g.nucleotide_seq
            d["protein_seq"] = g.protein_seq
        return d

    return {"predictor": body.predictor, "n_genes": len(preds), "genes": [row(g) for g in preds]}


@router.post("/annotation/genes/predict-fasta", tags=["Annotation"])
async def api_predict_genes_fasta(
    body: GenePredictFromFastaRequest,
    _auth: TokenPayload = Depends(get_tools_authorization),
):
    """Predict genes from in-memory FASTA (written to a temp file for parsing)."""
    import tempfile

    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".fa", delete=False, encoding="utf-8") as tmp:
            tmp.write(body.fasta)
            path = Path(tmp.name)
        try:
            result = annotate_fasta_path(
                path,
                predictor=body.predictor,
                include_sequences=body.include_sequences,
                use_prodigal_binary=body.use_prodigal_binary,
                prodigal_meta_mode=body.prodigal_meta_mode,
            )
        finally:
            path.unlink(missing_ok=True)
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    genes: List[Dict[str, Any]] = result["genes"]
    truncated = len(genes) > body.max_genes
    return {
        "predictor": body.predictor,
        "total_genes": result["total_genes"],
        "per_contig": result["per_contig"],
        "genes": genes[: body.max_genes],
        "genes_truncated": truncated,
        "gff": result["gff"] if not truncated else None,
    }


@router.post("/annotation/genes/assembly", tags=["Annotation"])
async def api_annotate_assembly_genes(
    body: AssemblyGeneAnnotateRequest,
    _auth: TokenPayload = Depends(get_tools_authorization),
):
    """Annotate contigs from an assembly (JSON list of contigs)."""
    from backend.assembly.assemblers import AssemblyResult, Contig

    try:
        contigs = [
            Contig(
                id=str(c["id"]),
                sequence=str(c["sequence"]),
                coverage=float(c.get("coverage", 0.0)),
            )
            for c in body.contigs
        ]
        ar = AssemblyResult(contigs=contigs)
        result = annotate_assembly_result(
            ar,
            predictor=body.predictor,
            include_sequences=body.include_sequences,
            use_prodigal_binary=body.use_prodigal_binary,
            prodigal_meta_mode=body.prodigal_meta_mode,
        )
    except (KeyError, ValueError, TypeError, RuntimeError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    return result


@router.post("/chemistry/md/run", tags=["Computational Chemistry"])
async def api_run_md(
    body: MDRunRequest,
    _auth: TokenPayload = Depends(get_tools_authorization),
    _: None = Depends(check_chemistry_tools_rate_limit),
):
    """Run molecular dynamics on a PDB structure."""
    from backend.computational_chemistry import (
        BerendsenThermostat,
        MDSimulation,
        Molecule,
        TrajectoryAnalyzer,
    )

    try:
        mol = Molecule.from_pdb(body.pdb)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid PDB: {e}") from e

    if mol.num_atoms == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No atoms parsed from PDB")

    md = MDSimulation(mol, thermostat=BerendsenThermostat(body.temperature, tau=0.5))
    md.initialize(box_size=body.box_size, temperature=body.temperature)
    if body.minimize_steps > 0:
        md.minimize_energy(max_steps=body.minimize_steps, tolerance=0.5)
    md.run(
        n_steps=body.n_steps,
        save_interval=body.save_interval,
        print_interval=body.n_steps + 1,
    )

    analyzer = TrajectoryAnalyzer(md.trajectory)
    ref = md.trajectory[0].positions if md.trajectory else mol.positions.copy()
    rmsd = analyzer.calculate_rmsd(ref).tolist() if md.trajectory else []
    rg = analyzer.calculate_radius_of_gyration().tolist() if md.trajectory else []
    estats = analyzer.energy_statistics() if md.trajectory else {}

    return {
        "n_atoms": mol.num_atoms,
        "n_frames": len(md.trajectory),
        "final_total_energy_kcal_mol": float(md.state.total_energy) if md.state else None,
        "final_temperature_K": float(md.state.temperature) if md.state else None,
        "rmsd": rmsd,
        "radius_of_gyration": rg,
        "energy_statistics": estats,
    }


@router.post("/chemistry/docking/run", tags=["Computational Chemistry"])
async def api_run_docking(
    body: DockingRunRequest,
    _auth: TokenPayload = Depends(get_tools_authorization),
    _: None = Depends(check_chemistry_tools_rate_limit),
):
    """Dock a ligand PDB to a receptor PDB."""
    from backend.computational_chemistry import MolecularDocking, Molecule

    try:
        protein = Molecule.from_pdb(body.protein_pdb)
        ligand = Molecule.from_pdb(body.ligand_pdb)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid PDB: {e}") from e

    if protein.num_atoms == 0 or ligand.num_atoms == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty protein or ligand")

    dock = MolecularDocking(exhaustiveness=body.exhaustiveness, n_poses=body.n_poses)
    site = binding_site_at_receptor_center(protein)
    poses = dock.dock(ligand, protein, binding_site=site)

    return {
        "n_poses": len(poses),
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
    }


@router.post("/chemistry/pipelines/structure-md-dock", tags=["Computational Chemistry"])
async def api_structure_md_dock(
    body: StructureMDDockRequest,
    _auth: TokenPayload = Depends(get_tools_authorization),
    _: None = Depends(check_chemistry_tools_rate_limit),
):
    """Run structure → MD → docking in one request."""
    try:
        result = run_structure_md_dock(
            body.protein_pdb,
            body.ligand_pdb,
            md_steps=body.md_steps,
            md_save_interval=body.md_save_interval,
            md_box_size=body.md_box_size,
            md_temperature=body.md_temperature,
            minimize_steps=body.minimize_steps,
            docking_poses=body.docking_poses,
            docking_exhaustiveness=body.docking_exhaustiveness,
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    return result


@router.get("/annotation/genes/predictors", tags=["Annotation"])
async def api_list_gene_predictors(
    _auth: TokenPayload = Depends(get_tools_authorization),
):
    """List supported gene predictor keys."""
    from backend.pipelines.gene_annotation import prodigal_binary_available

    return {
        "predictors": ["prodigal", "augustus", "glimmer", "metagene", "orf"],
        "prodigal_binary_on_path": prodigal_binary_available(),
    }

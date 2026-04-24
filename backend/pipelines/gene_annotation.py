"""Gene prediction helpers for assembly, FASTA annotation, and integration workflows."""

from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import unquote

logger = logging.getLogger(__name__)

import contextlib

from backend.annotation.gene_prediction import (
    AugustusPredictor,
    GenePrediction,
    GenePredictor,
    GlimmerPredictor,
    MetaGenePredictor,
    ORFFinder,
    ProdigalPredictor,
)
from backend.assembly.assemblers import AssemblyResult
from backend.bioinformatics.formats import FastaParser

_PREDICTOR_MAP = {
    "prodigal": ProdigalPredictor,
    "augustus": AugustusPredictor,
    "glimmer": GlimmerPredictor,
    "metagene": MetaGenePredictor,
    "orf": ORFFinder,
}


def get_gene_predictor(name: str, **kwargs: Any) -> GenePredictor:
    """Instantiate a gene predictor by short name."""
    key = name.lower().strip()
    cls = _PREDICTOR_MAP.get(key)
    if cls is None:
        allowed = ", ".join(sorted(_PREDICTOR_MAP))
        raise ValueError(f"Unknown gene predictor '{name}'. Choose one of: {allowed}")
    return cls(**kwargs)


def predict_genes_for_contig(
    sequence: str,
    contig_id: str,
    predictor: str = "prodigal",
    **predictor_kwargs: Any,
) -> list[GenePrediction]:
    """Run gene prediction on a single contig sequence."""
    p = get_gene_predictor(predictor, **predictor_kwargs)
    return p.predict(sequence.upper().replace(" ", "").replace("\n", ""), contig_id=contig_id)


def _gene_to_dict(g: GenePrediction, include_sequences: bool) -> dict[str, Any]:
    d: dict[str, Any] = {
        "id": g.id,
        "contig": g.contig,
        "start": g.start,
        "end": g.end,
        "strand": g.strand,
        "gene_type": g.gene_type,
        "score": g.score,
        "length": g.length,
        "locus_tag": g.locus_tag,
        "gene_name": g.gene_name,
        "product": g.product,
    }
    if include_sequences:
        d["nucleotide_seq"] = g.nucleotide_seq
        d["protein_seq"] = g.protein_seq
    return d


def annotate_assembly_result(
    assembly: AssemblyResult,
    predictor: str = "prodigal",
    include_sequences: bool = False,
    use_prodigal_binary: bool = False,
    prodigal_meta_mode: bool = False,
    **predictor_kwargs: Any,
) -> dict[str, Any]:
    """Predict genes on every contig in an assembly result.

    Returns summaries and concatenated GFF suitable for downstream annotation.
    """
    if use_prodigal_binary and predictor.lower() == "prodigal":
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".fa", delete=False, encoding="utf-8"
        ) as handle:
            for contig in assembly.contigs:
                handle.write(f">{contig.id}\n{contig.sequence}\n")
            fasta_tmp = Path(handle.name)
        try:
            return annotate_fasta_path(
                fasta_tmp,
                predictor="prodigal",
                include_sequences=include_sequences,
                use_prodigal_binary=True,
                prodigal_meta_mode=prodigal_meta_mode,
                **predictor_kwargs,
            )
        finally:
            fasta_tmp.unlink(missing_ok=True)

    all_predictions: list[GenePrediction] = []
    gff_lines: list[str] = ["##gff-version 3"]
    per_contig: list[dict[str, Any]] = []

    for contig in assembly.contigs:
        preds = predict_genes_for_contig(contig.sequence, contig.id, predictor, **predictor_kwargs)
        all_predictions.extend(preds)
        per_contig.append({"contig_id": contig.id, "n_genes": len(preds)})
        for g in preds:
            gff_lines.append(g.to_gff())

    return {
        "predictor": predictor,
        "total_genes": len(all_predictions),
        "per_contig": per_contig,
        "gff": "\n".join(gff_lines),
        "genes": [_gene_to_dict(g, include_sequences) for g in all_predictions],
    }


def prodigal_binary_available() -> bool:
    return shutil.which("prodigal") is not None


def _parse_gff_attributes(attr_col: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in attr_col.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        k, v = part.split("=", 1)
        out[k.strip()] = unquote(v.strip())
    return out


def _reverse_complement(sequence: str) -> str:
    comp = {"A": "T", "T": "A", "G": "C", "C": "G", "N": "N"}
    return "".join(comp.get(b, "N") for b in reversed(sequence.upper()))


def genes_from_prodigal_gff(
    gff_text: str,
    contig_sequences: dict[str, str] | None = None,
) -> tuple[list[GenePrediction], list[dict[str, Any]]]:
    """Parse Prodigal GFF3 (``-f gff``) CDS rows into :class:`GenePrediction` records.

    When ``contig_sequences`` is provided (record id -> uppercased sequence), fills
    ``nucleotide_seq`` for each CDS; ``protein_seq`` prefers the ``translation=`` attribute.
    """
    predictions: list[GenePrediction] = []
    order: list[str] = []
    seen_contig: set[str] = set()

    for raw in gff_text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        cols = line.split("\t")
        if len(cols) < 9:
            continue
        if cols[2].upper() != "CDS":
            continue

        contig = cols[0]
        try:
            start = int(cols[3])
            end = int(cols[4])
        except ValueError:
            continue

        strand = cols[6] if cols[6] in ("+", "-") else "+"
        attrs = _parse_gff_attributes(cols[8])

        score = 0.0
        if cols[5] not in ("", "."):
            try:
                score = float(cols[5])
            except ValueError:
                score = 0.0
        if score == 0.0 and "confidence" in attrs:
            with contextlib.suppress(ValueError):
                score = float(attrs["confidence"])

        gid = attrs.get("ID") or f"{contig}_cds_{len(predictions)}"
        protein_seq = attrs.get("translation", "").strip()
        if protein_seq.endswith("*"):
            protein_seq = protein_seq[:-1]

        nuc_seq = ""
        if contig_sequences:
            full = contig_sequences.get(contig)
            if full and start >= 1 and end <= len(full) and start <= end:
                slice_ = full[start - 1 : end]
                nuc_seq = _reverse_complement(slice_) if strand == "-" else slice_
                if not protein_seq:
                    tmp = ORFFinder(min_length=1)._translate(nuc_seq)
                    protein_seq = tmp.rstrip("*")

        predictions.append(
            GenePrediction(
                id=gid,
                contig=contig,
                start=start,
                end=end,
                strand=strand,
                gene_type="CDS",
                score=score,
                product=attrs.get("product", ""),
                locus_tag=attrs.get("locus_tag", gid),
                gene_name=attrs.get("Name", ""),
                nucleotide_seq=nuc_seq,
                protein_seq=protein_seq,
            )
        )
        if contig not in seen_contig:
            seen_contig.add(contig)
            order.append(contig)

    predictions.sort(key=lambda g: (g.contig, g.start, g.end))
    counts: dict[str, int] = defaultdict(int)
    for g in predictions:
        counts[g.contig] += 1
    per_contig = [{"contig_id": cid, "n_genes": counts[cid]} for cid in order]
    return predictions, per_contig


def run_prodigal_cli(fasta_path: Path, meta: bool = False) -> str:
    """Run Prodigal on a multi-FASTA file; return GFF3 text."""
    exe = shutil.which("prodigal")
    if not exe:
        raise RuntimeError("prodigal executable not found on PATH")
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "genes.gff"
        cmd = [exe, "-i", str(fasta_path), "-o", str(out), "-f", "gff", "-q"]
        if meta:
            cmd.extend(["-p", "meta"])
        subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=3600)
        return out.read_text(encoding="utf-8", errors="replace")


def annotate_fasta_path(
    fasta_path: str | Path,
    predictor: str = "prodigal",
    include_sequences: bool = False,
    gff_output: str | Path | None = None,
    use_prodigal_binary: bool = False,
    prodigal_meta_mode: bool = False,
    **predictor_kwargs: Any,
) -> dict[str, Any]:
    """Parse a FASTA file and run gene prediction on each record."""
    path = Path(fasta_path)

    if use_prodigal_binary and predictor.lower() == "prodigal":
        if not prodigal_binary_available():
            raise RuntimeError("use_prodigal_binary=True requires prodigal on PATH")
        gff_text = run_prodigal_cli(path, meta=prodigal_meta_mode)
        if gff_output:
            out = Path(gff_output)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(gff_text, encoding="utf-8")
        contig_seqs: dict[str, str] | None = None
        if include_sequences:
            contig_seqs = {}
            for record in FastaParser().parse(path):
                contig_seqs[record.id] = record.sequence.upper().replace(" ", "").replace("\n", "")

        preds, per_contig = genes_from_prodigal_gff(gff_text, contig_seqs)
        logger.info("Prodigal binary annotated %s (%s genes)", path, len(preds))
        return {
            "predictor": "prodigal",
            "prodigal_backend": "binary",
            "fasta_path": str(path.resolve()),
            "total_genes": len(preds),
            "per_contig": per_contig,
            "gff": gff_text,
            "gff_written": str(Path(gff_output).resolve()) if gff_output else None,
            "genes": [_gene_to_dict(g, include_sequences) for g in preds],
        }

    parser = FastaParser()
    all_predictions: list[GenePrediction] = []
    gff_lines: list[str] = ["##gff-version 3"]
    per_contig: list[dict[str, Any]] = []

    for record in parser.parse(path):
        seq = record.sequence.upper().replace(" ", "").replace("\n", "")
        if not seq:
            continue
        preds = predict_genes_for_contig(seq, record.id, predictor, **predictor_kwargs)
        all_predictions.extend(preds)
        per_contig.append({"contig_id": record.id, "n_genes": len(preds)})
        for g in preds:
            gff_lines.append(g.to_gff())

    gff_text = "\n".join(gff_lines)
    if gff_output:
        out = Path(gff_output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(gff_text, encoding="utf-8")

    return {
        "predictor": predictor,
        "fasta_path": str(path.resolve()),
        "total_genes": len(all_predictions),
        "per_contig": per_contig,
        "gff": gff_text,
        "gff_written": str(Path(gff_output).resolve()) if gff_output else None,
        "genes": [_gene_to_dict(g, include_sequences) for g in all_predictions],
    }


def integration_gene_annotation_summary(
    fasta_path: str | Path,
    predictor: str = "prodigal",
    max_genes_listed: int = 500,
    **predictor_kwargs: Any,
) -> dict[str, Any]:
    """Lightweight gene annotation block for multi-omics integration results.

    Omits full GFF in the returned dict when very large; callers may write GFF via annotate_fasta_path.
    """
    kw = dict(predictor_kwargs)
    use_bin = bool(kw.pop("use_prodigal_binary", False))
    meta = bool(kw.pop("prodigal_meta_mode", False))
    full = annotate_fasta_path(
        fasta_path,
        predictor=predictor,
        include_sequences=False,
        gff_output=None,
        use_prodigal_binary=use_bin,
        prodigal_meta_mode=meta,
        **kw,
    )
    genes = full["genes"]
    truncated = len(genes) > max_genes_listed
    return {
        "predictor": predictor,
        "fasta_path": full["fasta_path"],
        "total_genes": full["total_genes"],
        "per_contig": full["per_contig"],
        "gene_ids": [g["id"] for g in genes[:max_genes_listed]],
        "gene_ids_truncated": truncated,
        "gff_line_count": len(full["gff"].splitlines()),
    }

"""Tests for pipeline helpers (gene annotation, structure–MD–docking)."""

import textwrap

from backend.assembly.assemblers import AssemblyResult, Contig
from backend.pipelines.gene_annotation import (
    annotate_assembly_result,
    genes_from_prodigal_gff,
    predict_genes_for_contig,
)
from backend.computational_chemistry.docking import binding_site_at_receptor_center
from backend.pipelines.structure_md_dock import run_structure_md_dock


def test_predict_genes_orf_short_sequence():
    seq = "ATG" + ("AAC" * 40) + "TAA"
    preds = predict_genes_for_contig(seq, "c1", "orf")
    assert isinstance(preds, list)


def test_genes_from_prodigal_gff_shape():
    gff = textwrap.dedent(
        """\
        ##gff-version 3
        myctg\tProdigal_v2.6.3\tCDS\t1\t12\t.\t+\t0\tID=1_1;partial=00;confidence=99.0;translation=MWK
        other\tProdigal_v2.6.3\tCDS\t1\t9\t.\t+\t0\tID=2_1;partial=00;confidence=88.0;translation=MAA
        segc\tProdigal_v2.6.3\tCDS\t7\t15\t.\t-\t0\tID=3_1;partial=00;confidence=90.0;translation=MWK
        """
    ).strip()
    seq_c = "ATGTGGAAATAA"
    seq_o = "ATGGCTGCA"
    # Minus strand: genomic slice TTTCCACAT (coords 7–15) revcomp → ATGTGGAAA (MWK).
    # Six leading Ns so 1-based positions 7–15 land on TTTCCACAT (not on an N).
    seq_g = "NNNNNN" + "TTTCCACAT"
    preds, per = genes_from_prodigal_gff(
        gff,
        {"myctg": seq_c, "other": seq_o, "segc": seq_g.upper()},
    )
    assert len(preds) == 3
    assert preds[0].id == "1_1" and preds[0].strand == "+" and preds[0].start == 1 and preds[0].end == 12
    assert preds[0].nucleotide_seq == "ATGTGGAAATAA"
    assert preds[0].protein_seq == "MWK"
    assert preds[1].contig == "other" and preds[1].protein_seq == "MAA"
    assert preds[2].strand == "-"
    assert preds[2].nucleotide_seq == "ATGTGGAAA"
    assert per == [
        {"contig_id": "myctg", "n_genes": 1},
        {"contig_id": "other", "n_genes": 1},
        {"contig_id": "segc", "n_genes": 1},
    ]


def test_annotate_assembly_result():
    contigs = [Contig(id="ctg1", sequence="ATG" + ("AAC" * 50) + "TAA", coverage=10.0)]
    ar = AssemblyResult(contigs=contigs)
    out = annotate_assembly_result(ar, predictor="orf", include_sequences=False)
    assert "gff" in out
    assert out["total_genes"] >= 0


def test_binding_site_at_receptor_center():
    from backend.computational_chemistry import Molecule

    pdb = """ATOM      1  N   ALA A   1       0.000   0.000   0.000  1.00  0.00           N
ATOM      2  CA  ALA A   1       1.458   0.000   0.000  1.00  0.00           C
END
"""
    mol = Molecule.from_pdb(pdb)
    site = binding_site_at_receptor_center(mol)
    assert site.radius > 0


def test_structure_md_dock_minimal():
    protein = """ATOM      1  N   ALA A   1       0.000   0.000   0.000  1.00  0.00           N
ATOM      2  CA  ALA A   1       1.458   0.000   0.000  1.00  0.00           C
ATOM      3  C   ALA A   1       2.009   1.420   0.000  1.00  0.00           C
END
"""
    ligand = """HETATM  1  C1  LIG X   1      10.000  10.000  10.000  1.00  0.00           C
END
"""
    r = run_structure_md_dock(
        protein,
        ligand,
        md_steps=5,
        md_save_interval=1,
        minimize_steps=5,
        docking_poses=3,
        docking_exhaustiveness=2,
    )
    assert "md" in r and "docking" in r
    assert r["md"]["n_frames"] >= 0

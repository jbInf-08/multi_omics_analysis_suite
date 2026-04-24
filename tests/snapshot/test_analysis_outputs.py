"""Snapshot Tests for Analysis Outputs.
====================================

Tests that verify analysis outputs remain consistent across code changes.
Uses pytest-snapshot for comparing complex outputs.
"""

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

# Snapshot directory
SNAPSHOT_DIR = Path(__file__).parent / "snapshots"


def serialize_for_snapshot(obj: Any) -> str:
    """Serialize object for snapshot comparison."""
    if isinstance(obj, pd.DataFrame):
        return obj.to_json(orient="split", indent=2)
    elif isinstance(obj, np.ndarray):
        return json.dumps(obj.tolist(), indent=2)
    elif isinstance(obj, dict):
        return json.dumps(obj, indent=2, default=str)
    elif hasattr(obj, "__dict__"):
        return json.dumps(obj.__dict__, indent=2, default=str)
    else:
        return str(obj)


def load_snapshot(name: str) -> str:
    """Load snapshot from file."""
    snapshot_file = SNAPSHOT_DIR / f"{name}.snapshot"
    if snapshot_file.exists():
        return snapshot_file.read_text()
    return None


def save_snapshot(name: str, content: str):
    """Save snapshot to file."""
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    snapshot_file = SNAPSHOT_DIR / f"{name}.snapshot"
    snapshot_file.write_text(content)


def assert_snapshot(name: str, obj: Any, update: bool = False):
    """Assert object matches snapshot or update snapshot."""
    serialized = serialize_for_snapshot(obj)
    existing = load_snapshot(name)

    if existing is None or update:
        save_snapshot(name, serialized)
        if existing is None:
            pytest.skip(f"Snapshot '{name}' created. Run tests again to verify.")
    else:
        assert serialized == existing, f"Snapshot '{name}' does not match"


class TestSequenceAnalysisSnapshots:
    """Snapshot tests for sequence analysis outputs."""

    def test_gc_content_snapshot(self, sample_dna_sequences):
        """Test GC content calculation consistency."""
        from backend.bioinformatics.sequence import DNASequence

        results = {}
        for name, seq_str in sample_dna_sequences.items():
            if "N" not in seq_str:  # Skip sequences with N
                seq = DNASequence(seq_str)
                results[name] = {
                    "gc_content": round(seq.gc_content(), 4),
                    "length": len(seq),
                }

        assert_snapshot("gc_content_analysis", results)

    def test_translation_snapshot(self):
        """Test translation output consistency."""
        from backend.bioinformatics.sequence import DNASequence

        test_sequences = {
            "simple": "ATGAAAGGGCCC",
            "with_stop": "ATGAAATAGGGG",
            "longer": "ATGCGATCGATCGATCGATCGATCG",
        }

        results = {}
        for name, seq_str in test_sequences.items():
            dna = DNASequence(seq_str)
            protein = dna.translate()
            results[name] = {
                "dna": seq_str,
                "protein": str(protein),
                "protein_length": len(protein),
            }

        assert_snapshot("translation_results", results)

    def test_orf_finding_snapshot(self):
        """Test ORF finding consistency."""
        from backend.bioinformatics.sequence import DNASequence

        # Create sequence with clear ORFs
        test_seq = "AAATGAAAGGGCCCTTTTAAGGGG" * 5
        dna = DNASequence(test_seq)
        orfs = dna.find_orfs(min_length=15)

        # Simplify ORF data for snapshot
        simplified_orfs = [
            {
                "start": orf["start"],
                "end": orf["end"],
                "length": orf["length"],
                "strand": orf["strand"],
            }
            for orf in orfs
        ]

        assert_snapshot("orf_finding_results", simplified_orfs)


class TestAlignmentSnapshots:
    """Snapshot tests for alignment outputs."""

    def test_global_alignment_snapshot(self):
        """Test global alignment output consistency."""
        from backend.bioinformatics.algorithms import GlobalAligner

        test_cases = [
            ("ATGCGATCG", "ATGCGATCG"),
            ("ATGCGATCG", "ATGCGATTCG"),
            ("ATGCGATCGATCG", "ATGCGATCG"),
        ]

        aligner = GlobalAligner()
        results = {}

        for i, (seq1, seq2) in enumerate(test_cases):
            result = aligner.align(seq1, seq2)
            results[f"case_{i}"] = {
                "seq1": seq1,
                "seq2": seq2,
                "aligned1": result.seq1_aligned,
                "aligned2": result.seq2_aligned,
                "identity": round(result.identity, 4),
                "score": round(result.score, 2),
                "gaps": result.gaps,
            }

        assert_snapshot("global_alignment_results", results)

    def test_local_alignment_snapshot(self):
        """Test local alignment output consistency."""
        from backend.bioinformatics.algorithms import LocalAligner

        test_cases = [
            ("XXXXXATGCGATCGXXXXX", "YYYYYATGCGATCGYYYYY"),
            ("AAAATGCAAAA", "CCCCATGCCCCC"),
        ]

        aligner = LocalAligner()
        results = {}

        for i, (seq1, seq2) in enumerate(test_cases):
            result = aligner.align(seq1, seq2)
            results[f"case_{i}"] = {
                "identity": round(result.identity, 4),
                "score": round(result.score, 2),
                "alignment_length": result.alignment_length,
            }

        assert_snapshot("local_alignment_results", results)


class TestStatisticalAnalysisSnapshots:
    """Snapshot tests for statistical analysis outputs."""

    def test_effect_size_snapshot(self):
        """Test effect size calculation consistency."""
        from backend.analysis.statistical_analysis import EffectSizeCalculator

        np.random.seed(42)  # Reproducible

        # Create test groups
        group1 = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        group2 = np.array([3.0, 4.0, 5.0, 6.0, 7.0])

        results = {
            "cohens_d": round(EffectSizeCalculator.cohens_d(group1, group2)[0], 4),
            "hedges_g": round(EffectSizeCalculator.hedges_g(group1, group2)[0], 4),
            "cliffs_delta": round(EffectSizeCalculator.cliffs_delta(group1, group2)[0], 4),
        }

        assert_snapshot("effect_size_results", results)

    def test_multiple_testing_correction_snapshot(self):
        """Test multiple testing correction consistency."""
        from backend.analysis.statistical_analysis import MultipleTestingCorrection

        p_values = np.array([0.001, 0.01, 0.02, 0.03, 0.05, 0.1, 0.5])

        reject_bh, adjusted_bh, _, _ = MultipleTestingCorrection.correct(
            p_values, method="fdr_bh", alpha=0.05
        )

        reject_bonf, adjusted_bonf, _, _ = MultipleTestingCorrection.correct(
            p_values, method="bonferroni", alpha=0.05
        )

        results = {
            "p_values": p_values.tolist(),
            "bh_adjusted": [round(p, 6) for p in adjusted_bh],
            "bh_reject": reject_bh.tolist(),
            "bonferroni_adjusted": [round(p, 6) for p in adjusted_bonf],
            "bonferroni_reject": reject_bonf.tolist(),
        }

        assert_snapshot("multiple_testing_correction", results)

    def test_differential_expression_snapshot(self, expression_matrix, sample_groups):
        """Test differential expression analysis consistency."""
        from backend.analysis.statistical_analysis import differential_expression_analysis

        result = differential_expression_analysis(
            expression_matrix,
            sample_groups,
            fdr_threshold=0.05,
            log2fc_threshold=0.5,
        )

        # Get summary statistics
        summary = {
            "total_features": len(result),
            "significant_count": int(result["is_deg"].sum()),
            "upregulated_count": int((result["deg_class"] == "upregulated").sum()),
            "downregulated_count": int((result["deg_class"] == "downregulated").sum()),
            "top_5_features": result.head(5)["feature"].tolist(),
        }

        assert_snapshot("differential_expression_summary", summary)


class TestAssemblySnapshots:
    """Snapshot tests for assembly outputs."""

    def test_assembly_statistics_snapshot(self, fastq_reads):
        """Test assembly statistics consistency."""
        from backend.assembly.assemblers import DeBruijnAssembler

        assembler = DeBruijnAssembler(k=11)
        result = assembler.assemble(fastq_reads)

        summary = {
            "num_contigs": result.num_contigs,
            "total_length": result.total_length,
            "n50": result.n50,
            "largest_contig": result.largest_contig,
            "gc_content": round(result.gc_content, 4) if result.gc_content else 0,
        }

        assert_snapshot("assembly_statistics", summary)


class TestKmerAnalysisSnapshots:
    """Snapshot tests for k-mer analysis outputs."""

    def test_kmer_counting_snapshot(self):
        """Test k-mer counting consistency."""
        from backend.bioinformatics.algorithms import KmerCounter

        test_sequence = "ATGCGATCGATCGATCGATCGATCGATCGATCG"

        counter = KmerCounter(k=5, canonical=False)
        counts = counter.count_kmers(test_sequence)

        # Get top 10 k-mers by count
        sorted_kmers = sorted(counts.items(), key=lambda x: -x[1])[:10]

        results = {
            "sequence_length": len(test_sequence),
            "unique_kmers": len(counts),
            "top_10_kmers": sorted_kmers,
        }

        assert_snapshot("kmer_counting_results", results)

    def test_kmer_similarity_snapshot(self):
        """Test k-mer similarity consistency."""
        from backend.bioinformatics.algorithms import KmerCounter

        seq1 = "ATGCGATCGATCGATCGATCGATCG"
        seq2 = "ATGCGATCGATCGATCGTTTTTTTT"
        seq3 = "GGGGGGGGGGGGGGGGGGGGGGGG"

        counter = KmerCounter(k=5)

        results = {
            "seq1_vs_seq2_jaccard": round(
                counter.compare_sequences(seq1, seq2, method="jaccard"), 4
            ),
            "seq1_vs_seq3_jaccard": round(
                counter.compare_sequences(seq1, seq3, method="jaccard"), 4
            ),
            "seq1_vs_seq1_jaccard": round(
                counter.compare_sequences(seq1, seq1, method="jaccard"), 4
            ),
        }

        assert_snapshot("kmer_similarity_results", results)


class TestMotifFindingSnapshots:
    """Snapshot tests for motif finding outputs."""

    def test_motif_finding_snapshot(self):
        """Test motif finding consistency."""
        from backend.bioinformatics.algorithms import MotifFinder

        sequences = [
            "ATGCGATCGATCG",
            "GATCGATCGATCG",
            "ATGCGATCGAAAA",
            "XXXXGATCXXXX",
        ]

        finder = MotifFinder()

        # Find exact motifs
        exact_motifs = finder.find_exact_motifs(sequences, motif_length=4, min_occurrences=2)

        # Get consensus
        consensus, pwm = finder.find_consensus_motif(sequences, motif_length=4)

        results = {
            "exact_motifs_count": len(exact_motifs),
            "top_motifs": exact_motifs[:5],
            "consensus": consensus,
        }

        assert_snapshot("motif_finding_results", results)


# Utility for updating all snapshots
def update_all_snapshots():
    """Update all snapshots (run with --update-snapshots flag)."""
    import os

    os.environ["UPDATE_SNAPSHOTS"] = "1"


# pytest fixture to enable snapshot updates via command line
@pytest.fixture(scope="session", autouse=True)
def check_snapshot_update(request):
    """Check if snapshots should be updated."""
    import os

    if request.config.getoption("--update-snapshots", default=False):
        os.environ["UPDATE_SNAPSHOTS"] = "1"


def pytest_addoption(parser):
    """Add --update-snapshots option to pytest."""
    parser.addoption(
        "--update-snapshots", action="store_true", default=False, help="Update snapshot files"
    )

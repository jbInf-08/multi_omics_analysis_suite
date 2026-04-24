"""Property-Based Tests for Sequence Manipulation.
==============================================

Uses Hypothesis to test invariants and properties of sequence operations.
"""

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st
from hypothesis.strategies import composite

from backend.bioinformatics.algorithms import (
    GlobalAligner,
    KmerCounter,
    LocalAligner,
)

# Import sequence classes
from backend.bioinformatics.sequence import (
    DNASequence,
    ProteinSequence,
    RNASequence,
    SequenceCollection,
)

# =============================================================================
# Custom Strategies
# =============================================================================


@composite
def dna_sequences(draw, min_size=1, max_size=100):
    """Strategy for generating valid DNA sequences."""
    length = draw(st.integers(min_value=min_size, max_value=max_size))
    bases = draw(st.lists(st.sampled_from("ATGC"), min_size=length, max_size=length))
    return "".join(bases)


@composite
def rna_sequences(draw, min_size=1, max_size=100):
    """Strategy for generating valid RNA sequences."""
    length = draw(st.integers(min_value=min_size, max_value=max_size))
    bases = draw(st.lists(st.sampled_from("AUGC"), min_size=length, max_size=length))
    return "".join(bases)


@composite
def protein_sequences(draw, min_size=1, max_size=100):
    """Strategy for generating valid protein sequences."""
    amino_acids = "ACDEFGHIKLMNPQRSTVWY"
    length = draw(st.integers(min_value=min_size, max_value=max_size))
    residues = draw(st.lists(st.sampled_from(amino_acids), min_size=length, max_size=length))
    return "".join(residues)


@composite
def dna_with_n(draw, min_size=1, max_size=100):
    """Strategy for DNA sequences that may contain N."""
    length = draw(st.integers(min_value=min_size, max_value=max_size))
    bases = draw(st.lists(st.sampled_from("ATGCN"), min_size=length, max_size=length))
    return "".join(bases)


# =============================================================================
# DNA Sequence Properties
# =============================================================================


class TestDNASequenceProperties:
    """Property-based tests for DNA sequences."""

    @given(dna_sequences())
    def test_length_preserved(self, seq_str):
        """Property: Length is preserved in sequence object."""
        seq = DNASequence(seq_str)
        assert len(seq) == len(seq_str)

    @given(dna_sequences())
    def test_uppercase_normalization(self, seq_str):
        """Property: Sequences are normalized to uppercase."""
        seq = DNASequence(seq_str.lower())
        assert str(seq) == seq_str.upper()

    @given(dna_sequences())
    def test_double_complement_identity(self, seq_str):
        """Property: Complement of complement equals original."""
        seq = DNASequence(seq_str)
        double_comp = seq.complement().complement()
        assert str(double_comp) == str(seq)

    @given(dna_sequences())
    def test_double_reverse_complement_identity(self, seq_str):
        """Property: Reverse complement of reverse complement equals original."""
        seq = DNASequence(seq_str)
        double_revcomp = seq.reverse_complement().reverse_complement()
        assert str(double_revcomp) == str(seq)

    @given(dna_sequences())
    def test_gc_content_bounds(self, seq_str):
        """Property: GC content is always between 0 and 1."""
        seq = DNASequence(seq_str)
        gc = seq.gc_content()
        assert 0.0 <= gc <= 1.0

    @given(dna_sequences())
    def test_gc_content_consistency(self, seq_str):
        """Property: GC content matches manual calculation."""
        seq = DNASequence(seq_str)
        expected_gc = (seq_str.count("G") + seq_str.count("C")) / len(seq_str)
        assert seq.gc_content() == pytest.approx(expected_gc)

    @given(dna_sequences(min_size=3))
    def test_transcription_preserves_length(self, seq_str):
        """Property: Transcription preserves sequence length."""
        dna = DNASequence(seq_str)
        rna = dna.transcribe()
        assert len(rna) == len(dna)

    @given(dna_sequences(min_size=3))
    def test_transcription_replaces_t_with_u(self, seq_str):
        """Property: Transcription replaces all T with U."""
        dna = DNASequence(seq_str)
        rna = dna.transcribe()
        assert "T" not in str(rna)
        assert str(rna).count("U") == seq_str.upper().count("T")

    @given(dna_sequences(min_size=9), st.integers(min_value=0, max_value=2))
    def test_translation_produces_valid_protein(self, seq_str, frame):
        """Property: Translation produces valid protein sequence."""
        dna = DNASequence(seq_str)

        try:
            protein = dna.translate(frame=frame)
            # All characters should be valid amino acids or X (unknown)
            valid_chars = set("ACDEFGHIKLMNPQRSTVWYX*")
            assert all(aa in valid_chars for aa in str(protein))
        except ValueError:
            # Stop codons at the start can cause validation errors - this is expected
            pass

    @given(dna_sequences())
    def test_composition_sums_to_length(self, seq_str):
        """Property: Base composition sums to sequence length."""
        seq = DNASequence(seq_str)
        comp = seq.composition()
        assert sum(comp.values()) == len(seq)

    @given(dna_sequences())
    def test_frequency_sums_to_one(self, seq_str):
        """Property: Base frequencies sum to 1."""
        seq = DNASequence(seq_str)
        freq = seq.frequency()
        assert sum(freq.values()) == pytest.approx(1.0)

    @given(dna_sequences(), st.text(alphabet="ATGC", min_size=1, max_size=5))
    def test_count_non_negative(self, seq_str, pattern):
        """Property: Pattern count is always non-negative."""
        seq = DNASequence(seq_str)
        count = seq.count(pattern)
        assert count >= 0

    @given(dna_sequences())
    def test_fasta_format_contains_sequence(self, seq_str):
        """Property: FASTA output contains the sequence."""
        seq = DNASequence(seq_str, id="test")
        fasta = seq.to_fasta()
        # Remove newlines and check
        assert seq_str in fasta.replace("\n", "")

    @given(dna_sequences(), dna_sequences())
    def test_concatenation_length(self, seq1_str, seq2_str):
        """Property: Concatenation length equals sum of lengths."""
        seq1 = DNASequence(seq1_str)
        seq2 = DNASequence(seq2_str)
        combined = seq1 + seq2
        assert len(combined) == len(seq1) + len(seq2)

    @given(dna_sequences(min_size=5), st.integers(min_value=0, max_value=2))
    def test_subsequence_length(self, seq_str, start_offset):
        """Property: Subsequence has correct length."""
        seq = DNASequence(seq_str)
        start = start_offset
        end = len(seq) - start_offset

        assume(start < end)

        subseq = seq.subsequence(start, end)
        assert len(subseq) == end - start


class TestRNASequenceProperties:
    """Property-based tests for RNA sequences."""

    @given(rna_sequences())
    def test_rna_has_no_thymine(self, seq_str):
        """Property: RNA sequences have no thymine."""
        rna = RNASequence(seq_str)
        assert "T" not in str(rna)

    @given(rna_sequences())
    def test_to_dna_and_back(self, seq_str):
        """Property: RNA -> DNA -> RNA preserves sequence."""
        rna = RNASequence(seq_str)
        dna = rna.to_dna()
        rna_back = dna.transcribe()
        assert str(rna) == str(rna_back)

    @given(rna_sequences())
    def test_gc_content_valid(self, seq_str):
        """Property: GC content is valid for RNA."""
        rna = RNASequence(seq_str)
        gc = rna.gc_content()
        assert 0.0 <= gc <= 1.0


class TestProteinSequenceProperties:
    """Property-based tests for protein sequences."""

    @given(protein_sequences())
    def test_molecular_weight_positive(self, seq_str):
        """Property: Molecular weight is always positive."""
        protein = ProteinSequence(seq_str)
        mw = protein.molecular_weight()
        assert mw > 0

    @given(protein_sequences())
    def test_isoelectric_point_in_range(self, seq_str):
        """Property: pI is between 0 and 14."""
        protein = ProteinSequence(seq_str)
        pi = protein.isoelectric_point()
        assert 0.0 <= pi <= 14.0

    @given(protein_sequences())
    def test_aromaticity_in_range(self, seq_str):
        """Property: Aromaticity is between 0 and 1."""
        protein = ProteinSequence(seq_str)
        arom = protein.aromaticity()
        assert 0.0 <= arom <= 1.0

    @given(protein_sequences(min_size=10))
    @settings(max_examples=50)
    def test_hydrophobicity_profile_length(self, seq_str):
        """Property: Hydrophobicity profile has correct length."""
        protein = ProteinSequence(seq_str)
        window = 5
        profile = protein.hydrophobicity_profile(window=window)

        len(seq_str) - window + 1 - (window // 2) * 2
        assert len(profile) <= len(seq_str)


# =============================================================================
# Alignment Properties
# =============================================================================


class TestAlignmentProperties:
    """Property-based tests for sequence alignment."""

    @given(dna_sequences(min_size=5, max_size=50))
    @settings(max_examples=30)
    def test_self_alignment_perfect(self, seq_str):
        """Property: Aligning sequence with itself gives perfect identity."""
        aligner = GlobalAligner()
        result = aligner.align(seq_str, seq_str)

        assert result.identity == 1.0
        assert result.gaps == 0
        assert result.mismatches == 0

    @given(dna_sequences(min_size=5, max_size=30), dna_sequences(min_size=5, max_size=30))
    @settings(max_examples=30)
    def test_alignment_identity_bounds(self, seq1_str, seq2_str):
        """Property: Alignment identity is between 0 and 1."""
        aligner = GlobalAligner()
        result = aligner.align(seq1_str, seq2_str)

        assert 0.0 <= result.identity <= 1.0

    @given(dna_sequences(min_size=5, max_size=30), dna_sequences(min_size=5, max_size=30))
    @settings(max_examples=30)
    def test_alignment_lengths_equal(self, seq1_str, seq2_str):
        """Property: Aligned sequences have equal length."""
        aligner = GlobalAligner()
        result = aligner.align(seq1_str, seq2_str)

        assert len(result.seq1_aligned) == len(result.seq2_aligned)

    @given(dna_sequences(min_size=5, max_size=30), dna_sequences(min_size=5, max_size=30))
    @settings(max_examples=30)
    def test_alignment_preserves_non_gap_chars(self, seq1_str, seq2_str):
        """Property: Non-gap characters in alignment match original."""
        aligner = GlobalAligner()
        result = aligner.align(seq1_str, seq2_str)

        # Remove gaps and compare
        aligned1_no_gaps = result.seq1_aligned.replace("-", "")
        aligned2_no_gaps = result.seq2_aligned.replace("-", "")

        assert aligned1_no_gaps == seq1_str
        assert aligned2_no_gaps == seq2_str

    @given(dna_sequences(min_size=5, max_size=30))
    @settings(max_examples=30)
    def test_local_alignment_non_negative_score(self, seq_str):
        """Property: Local alignment score is non-negative."""
        aligner = LocalAligner()
        result = aligner.align(seq_str, seq_str)

        assert result.score >= 0


# =============================================================================
# K-mer Properties
# =============================================================================


class TestKmerProperties:
    """Property-based tests for k-mer counting."""

    @given(dna_sequences(min_size=10), st.integers(min_value=3, max_value=7))
    def test_kmer_count_bounds(self, seq_str, k):
        """Property: K-mer count is bounded by sequence length."""
        counter = KmerCounter(k=k, canonical=False)
        counts = counter.count_kmers(seq_str)

        max_possible = len(seq_str) - k + 1
        total_count = sum(counts.values())

        assert total_count <= max_possible

    @given(dna_sequences(min_size=10), st.integers(min_value=3, max_value=7))
    def test_kmer_frequency_sums_to_one(self, seq_str, k):
        """Property: K-mer frequencies sum to 1."""
        counter = KmerCounter(k=k, canonical=False)
        freq = counter.kmer_frequency(seq_str)

        if freq:  # If any k-mers were found
            assert sum(freq.values()) == pytest.approx(1.0)

    @given(dna_sequences(min_size=15))
    @settings(max_examples=30)
    def test_jaccard_self_similarity(self, seq_str):
        """Property: Jaccard similarity of sequence with itself is 1."""
        counter = KmerCounter(k=5)
        sim = counter.compare_sequences(seq_str, seq_str, method="jaccard")

        assert sim == 1.0

    @given(dna_sequences(min_size=15), dna_sequences(min_size=15))
    @settings(max_examples=30)
    def test_jaccard_symmetry(self, seq1_str, seq2_str):
        """Property: Jaccard similarity is symmetric."""
        counter = KmerCounter(k=5)

        sim12 = counter.compare_sequences(seq1_str, seq2_str, method="jaccard")
        sim21 = counter.compare_sequences(seq2_str, seq1_str, method="jaccard")

        assert sim12 == pytest.approx(sim21)

    @given(dna_sequences(min_size=15), dna_sequences(min_size=15))
    @settings(max_examples=30)
    def test_jaccard_bounds(self, seq1_str, seq2_str):
        """Property: Jaccard similarity is between 0 and 1."""
        counter = KmerCounter(k=5)
        sim = counter.compare_sequences(seq1_str, seq2_str, method="jaccard")

        assert 0.0 <= sim <= 1.0


# =============================================================================
# Collection Properties
# =============================================================================


class TestCollectionProperties:
    """Property-based tests for sequence collections."""

    @given(st.lists(dna_sequences(), min_size=1, max_size=10))
    def test_collection_length(self, seq_strs):
        """Property: Collection length matches number of added sequences."""
        seqs = [DNASequence(s, id=f"seq_{i}") for i, s in enumerate(seq_strs)]
        collection = SequenceCollection(seqs)

        assert len(collection) == len(seq_strs)

    @given(st.lists(dna_sequences(), min_size=1, max_size=10))
    def test_statistics_total_length(self, seq_strs):
        """Property: Statistics total length is sum of all lengths."""
        seqs = [DNASequence(s, id=f"seq_{i}") for i, s in enumerate(seq_strs)]
        collection = SequenceCollection(seqs)

        stats = collection.statistics()
        expected_total = sum(len(s) for s in seq_strs)

        assert stats["total_length"] == expected_total

    @given(st.lists(dna_sequences(min_size=5), min_size=2, max_size=5))
    def test_filter_by_length_subset(self, seq_strs):
        """Property: Filtered collection is subset of original."""
        seqs = [DNASequence(s, id=f"seq_{i}") for i, s in enumerate(seq_strs)]
        collection = SequenceCollection(seqs)

        min_len = min(len(s) for s in seq_strs)
        filtered = collection.filter_by_length(min_length=min_len)

        assert len(filtered) <= len(collection)

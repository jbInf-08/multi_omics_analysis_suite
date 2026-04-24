"""Unit Tests for Bioinformatics Algorithms.
========================================

Tests for alignment, motif finding, k-mer analysis, and index structures.
"""

import pytest

from backend.bioinformatics.algorithms import (
    AlignmentResult,
    BurrowsWheelerTransform,
    GlobalAligner,
    KmerCounter,
    LocalAligner,
    MotifFinder,
    MultipleSequenceAligner,
    ScoringMatrix,
    SuffixArray,
)


class TestScoringMatrix:
    """Tests for scoring matrix."""

    def test_simple_scoring(self):
        """Test simple match/mismatch scoring."""
        matrix = ScoringMatrix("simple")

        assert matrix.score("A", "A") > 0  # Match
        assert matrix.score("A", "T") < 0  # Mismatch

    def test_dna_scoring(self):
        """Test DNA-specific scoring."""
        matrix = ScoringMatrix("dna")

        assert matrix.score("A", "A") == 1
        assert matrix.score("A", "T") == -1

    def test_case_insensitivity(self):
        """Test case insensitivity."""
        matrix = ScoringMatrix("simple")

        assert matrix.score("a", "A") == matrix.score("A", "A")
        assert matrix.score("a", "t") == matrix.score("A", "T")


class TestGlobalAligner:
    """Tests for Needleman-Wunsch global alignment."""

    def test_identical_sequences(self):
        """Test alignment of identical sequences."""
        aligner = GlobalAligner()
        result = aligner.align("ATGC", "ATGC")

        assert result.identity == 1.0
        assert result.gaps == 0
        assert result.mismatches == 0
        assert result.seq1_aligned == "ATGC"
        assert result.seq2_aligned == "ATGC"

    def test_one_mismatch(self):
        """Test alignment with single mismatch."""
        aligner = GlobalAligner()
        result = aligner.align("ATGC", "ATAC")

        assert result.mismatches == 1
        assert result.gaps == 0
        assert result.identity == 0.75

    def test_one_gap(self):
        """Test alignment requiring one gap."""
        aligner = GlobalAligner()
        result = aligner.align("ATGC", "ATGCC")

        assert result.gaps >= 1
        assert "-" in result.seq1_aligned or "-" in result.seq2_aligned

    def test_longer_sequences(self):
        """Test alignment of longer sequences."""
        aligner = GlobalAligner()
        seq1 = "ATGCGATCGATCGATCG"
        seq2 = "ATGCGATTGATCGATCG"

        result = aligner.align(seq1, seq2)

        assert result.alignment_length >= max(len(seq1), len(seq2))
        assert 0 < result.identity < 1.0

    def test_completely_different(self):
        """Test alignment of very different sequences."""
        aligner = GlobalAligner()
        result = aligner.align("AAAA", "CCCC")

        assert result.identity < 0.5  # Low identity expected

    def test_alignment_score_positive_for_matches(self):
        """Test that matching sequences have positive score."""
        aligner = GlobalAligner()
        result = aligner.align("ATGCGATCG", "ATGCGATCG")

        assert result.score > 0

    def test_custom_penalties(self):
        """Test alignment with custom penalties."""
        aligner = GlobalAligner(match=5, mismatch=-2, gap_open=-10, gap_extend=-2)
        result = aligner.align("ATGC", "ATGC")

        # Score should reflect custom match score
        assert result.score > 0

    def test_alignment_result_str(self):
        """Test alignment result string representation."""
        aligner = GlobalAligner()
        result = aligner.align("ATGC", "ATAC")

        output = str(result)

        assert "Score:" in output
        assert "Identity:" in output


class TestLocalAligner:
    """Tests for Smith-Waterman local alignment."""

    def test_find_local_match(self):
        """Test finding local matching region."""
        aligner = LocalAligner()

        # Local match in the middle
        seq1 = "XXXXXATGCGATCGXXXXX"
        seq2 = "YYYYYATGCGATCGYYYYY"

        result = aligner.align(seq1, seq2)

        # Should find the matching region
        assert result.identity > 0.5
        assert result.score > 0

    def test_no_match_gives_low_score(self):
        """Test that non-matching sequences give low/zero score."""
        aligner = LocalAligner()
        result = aligner.align("AAAA", "CCCC")

        # With no matches possible, score should be 0
        assert result.score == 0 or result.alignment_length == 0

    def test_local_vs_global(self):
        """Test that local alignment finds best local region."""
        global_aligner = GlobalAligner()
        local_aligner = LocalAligner()

        # Sequences with good local match but poor global alignment
        seq1 = "AAAAAATGCGATCGAAAAA"
        seq2 = "CCCCATGCGATCGCCCCC"

        global_result = global_aligner.align(seq1, seq2)
        local_result = local_aligner.align(seq1, seq2)

        # Local alignment should have higher identity for matched region
        assert local_result.identity >= global_result.identity

    def test_start_end_positions(self):
        """Test that start/end positions are correctly set."""
        aligner = LocalAligner()

        seq1 = "XXXXATGCXXXX"
        seq2 = "YYYYATGCYYYY"

        result = aligner.align(seq1, seq2)

        # Positions should be valid indices
        assert 0 <= result.start1 <= result.end1 <= len(seq1)
        assert 0 <= result.start2 <= result.end2 <= len(seq2)


class TestMultipleSequenceAligner:
    """Tests for multiple sequence alignment."""

    def test_align_two_sequences(self):
        """Test MSA with just two sequences."""
        aligner = MultipleSequenceAligner()
        sequences = ["ATGCGATCG", "ATGCGATCG"]

        aligned = aligner.align(sequences)

        assert len(aligned) == 2

    def test_align_multiple_sequences(self):
        """Test MSA with multiple sequences."""
        aligner = MultipleSequenceAligner()
        sequences = [
            "ATGCGATCGATCG",
            "ATGCGATTGATCG",
            "ATGCGATCGATTG",
        ]

        aligned = aligner.align(sequences)

        assert len(aligned) == 3
        # All aligned sequences should have same length
        lengths = [len(seq) for seq in aligned]
        assert len(set(lengths)) == 1

    def test_single_sequence(self):
        """Test MSA with single sequence returns unchanged."""
        aligner = MultipleSequenceAligner()
        sequences = ["ATGCGATCG"]

        aligned = aligner.align(sequences)

        assert aligned == sequences


class TestMotifFinder:
    """Tests for motif finding algorithms."""

    def test_find_exact_motifs(self):
        """Test finding exact motifs."""
        finder = MotifFinder()
        sequences = [
            "ATGCGATCGATCG",
            "GATCGATCGATCG",
            "ATGCGATCGAAAA",
        ]

        motifs = finder.find_exact_motifs(sequences, motif_length=4, min_occurrences=2)

        assert len(motifs) > 0
        # "GATC" should be found in all sequences
        gatc_found = any(m[0] == "GATC" for m in motifs)
        assert gatc_found

    def test_find_consensus_motif(self):
        """Test finding consensus motif."""
        finder = MotifFinder()
        sequences = [
            "ATGCGATCG",
            "ATGCGATCG",
            "ATGCGATCG",
        ]

        consensus, pwm = finder.find_consensus_motif(sequences, motif_length=4)

        assert len(consensus) == 4
        assert pwm.shape == (4, 4)  # 4 bases x 4 positions

    def test_score_motif(self):
        """Test PWM scoring."""
        finder = MotifFinder()
        sequences = ["ATGC"] * 10

        consensus, pwm = finder.find_consensus_motif(sequences, motif_length=4)

        # Perfect match should have high score
        score_perfect = finder.score_motif("ATGC", pwm)
        score_mismatch = finder.score_motif("AAAA", pwm)

        assert score_perfect > score_mismatch

    def test_find_motif_occurrences(self):
        """Test finding motif occurrences above threshold."""
        finder = MotifFinder()

        # Create PWM from training sequences
        training = ["ATGC"] * 10
        _, pwm = finder.find_consensus_motif(training, motif_length=4)

        # Search in sequence
        test_seq = "AAAATGCAAAAATGCAAA"
        occurrences = finder.find_motif_occurrences(test_seq, pwm, threshold=0)

        # Should find the ATGC occurrences
        assert len(occurrences) >= 2


class TestKmerCounter:
    """Tests for k-mer counting and analysis."""

    def test_count_kmers(self):
        """Test basic k-mer counting."""
        counter = KmerCounter(k=3, canonical=False)
        sequence = "ATGATGATG"

        counts = counter.count_kmers(sequence)

        assert "ATG" in counts
        assert counts["ATG"] == 3

    def test_canonical_kmers(self):
        """Test canonical k-mer counting."""
        counter = KmerCounter(k=3, canonical=True)

        # ATG and its reverse complement CAT
        sequence = "ATGCAT"
        counts = counter.count_kmers(sequence)

        # With canonical, one should be counted
        assert len(counts) <= 4  # At most 4 distinct 3-mers

    def test_kmer_with_n(self):
        """Test that k-mers with N are skipped."""
        counter = KmerCounter(k=3, canonical=False)
        sequence = "ATGNGATG"

        counts = counter.count_kmers(sequence)

        # K-mers containing N should be excluded
        for kmer in counts:
            assert "N" not in kmer

    def test_kmer_frequency(self):
        """Test k-mer frequency calculation."""
        counter = KmerCounter(k=2, canonical=False)
        sequence = "ATATATAT"

        freq = counter.kmer_frequency(sequence)

        assert sum(freq.values()) == pytest.approx(1.0)

    def test_compare_sequences_jaccard(self):
        """Test Jaccard similarity between sequences."""
        counter = KmerCounter(k=3)

        # Identical sequences
        sim_identical = counter.compare_sequences("ATGCGATCG", "ATGCGATCG", method="jaccard")
        assert sim_identical == 1.0

        # Different sequences
        sim_different = counter.compare_sequences("ATGCGATCG", "TTTTTTTT", method="jaccard")
        assert sim_different < 1.0

    def test_compare_sequences_cosine(self):
        """Test cosine similarity between sequences."""
        counter = KmerCounter(k=3)

        sim = counter.compare_sequences("ATGCGATCG", "ATGCGATCG", method="cosine")
        assert sim == pytest.approx(1.0)

    def test_sketch(self):
        """Test MinHash sketch creation."""
        counter = KmerCounter(k=5)
        sequence = "ATGCGATCGATCGATCGATCGATCGATCGATCG"

        sketch = counter.sketch(sequence, sketch_size=10)

        assert len(sketch) <= 10

    def test_estimate_similarity(self):
        """Test similarity estimation from sketches."""
        counter = KmerCounter(k=5)

        seq1 = "ATGCGATCGATCGATCGATCGATCGATCGATCG"
        seq2 = "ATGCGATCGATCGATCGATCGATCGATCGATCG"

        sketch1 = counter.sketch(seq1, sketch_size=20)
        sketch2 = counter.sketch(seq2, sketch_size=20)

        sim = counter.estimate_similarity(sketch1, sketch2)
        assert sim == 1.0  # Identical sequences


class TestBurrowsWheelerTransform:
    """Tests for BWT and FM-index."""

    def test_bwt_creation(self):
        """Test BWT creation."""
        bwt = BurrowsWheelerTransform("BANANA")

        assert bwt.original == "BANANA"
        assert len(bwt.bwt) == len("BANANA") + 1  # Including $

    def test_search_existing_pattern(self):
        """Test searching for existing pattern."""
        bwt = BurrowsWheelerTransform("BANANA")

        # "ANA" appears twice in BANANA
        positions = bwt.search("ANA")

        assert len(positions) >= 1

    def test_search_nonexistent_pattern(self):
        """Test searching for non-existent pattern."""
        bwt = BurrowsWheelerTransform("BANANA")

        positions = bwt.search("XYZ")

        assert len(positions) == 0

    def test_search_single_char(self):
        """Test searching for single character."""
        bwt = BurrowsWheelerTransform("BANANA")

        positions = bwt.search("A")

        assert len(positions) == 3  # A appears 3 times


class TestSuffixArray:
    """Tests for suffix array."""

    def test_suffix_array_creation(self):
        """Test suffix array creation."""
        sa = SuffixArray("BANANA")

        assert len(sa.sa) == len("BANANA")
        assert len(sa.lcp) == len("BANANA")

    def test_search_existing(self):
        """Test searching existing pattern."""
        sa = SuffixArray("BANANA")

        positions = sa.search("ANA")

        # Verify positions are correct
        for pos in positions:
            assert "BANANA"[pos : pos + 3] == "ANA"

    def test_search_nonexistent(self):
        """Test searching non-existent pattern."""
        sa = SuffixArray("BANANA")

        positions = sa.search("XYZ")

        assert len(positions) == 0

    def test_longest_repeated_substring(self):
        """Test finding longest repeated substring."""
        sa = SuffixArray("BANANA")

        lrs = sa.longest_repeated_substring()

        # "ANA" or "AN" should be found
        assert len(lrs) >= 2

    def test_suffix_array_ordering(self):
        """Test that suffix array is properly sorted."""
        text = "BANANA"
        sa = SuffixArray(text)

        # Each suffix at position sa[i] should be <= suffix at sa[i+1]
        for i in range(len(sa.sa) - 1):
            suffix1 = text[sa.sa[i] :]
            suffix2 = text[sa.sa[i + 1] :]
            assert suffix1 <= suffix2


class TestAlignmentResult:
    """Tests for AlignmentResult dataclass."""

    def test_alignment_result_creation(self):
        """Test creating alignment result."""
        result = AlignmentResult(
            seq1_aligned="ATGC",
            seq2_aligned="AT-C",
            score=5.0,
            identity=0.75,
            gaps=1,
            mismatches=0,
            alignment_length=4,
        )

        assert result.score == 5.0
        assert result.identity == 0.75
        assert result.gaps == 1

    def test_alignment_str_output(self):
        """Test string representation of alignment."""
        result = AlignmentResult(
            seq1_aligned="ATGC",
            seq2_aligned="ATGC",
            score=8.0,
            identity=1.0,
            gaps=0,
            mismatches=0,
            alignment_length=4,
        )

        output = str(result)

        assert "ATGC" in output
        assert "Score: 8.0" in output
        assert "100.0%" in output  # Identity

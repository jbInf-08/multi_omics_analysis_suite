"""Bioinformatics Algorithms.
=========================

Core algorithms for sequence alignment, motif finding, and k-mer analysis.
"""

from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass

import numpy as np


@dataclass
class AlignmentResult:
    """Result of sequence alignment."""

    seq1_aligned: str
    seq2_aligned: str
    score: float
    identity: float
    gaps: int
    mismatches: int
    alignment_length: int
    start1: int = 0
    end1: int = 0
    start2: int = 0
    end2: int = 0
    cigar: str | None = None

    def __str__(self) -> str:
        """Pretty print alignment."""
        lines = []
        match_line = ""

        for a, b in zip(self.seq1_aligned, self.seq2_aligned, strict=False):
            if a == b:
                match_line += "|"
            elif a == "-" or b == "-":
                match_line += " "
            else:
                match_line += "."

        # Format in blocks of 60
        for i in range(0, len(self.seq1_aligned), 60):
            lines.append(f"Seq1: {self.seq1_aligned[i:i+60]}")
            lines.append(f"      {match_line[i:i+60]}")
            lines.append(f"Seq2: {self.seq2_aligned[i:i+60]}")
            lines.append("")

        lines.append(f"Score: {self.score}")
        lines.append(f"Identity: {self.identity:.1%}")
        lines.append(f"Gaps: {self.gaps}")

        return "\n".join(lines)


class ScoringMatrix:
    """Scoring matrix for sequence alignment."""

    # BLOSUM62 matrix for protein alignment
    BLOSUM62 = {
        ("A", "A"): 4,
        ("A", "R"): -1,
        ("A", "N"): -2,
        ("A", "D"): -2,
        ("A", "C"): 0,
        ("A", "Q"): -1,
        ("A", "E"): -1,
        ("A", "G"): 0,
        ("A", "H"): -2,
        ("A", "I"): -1,
        ("A", "L"): -1,
        ("A", "K"): -1,
        ("A", "M"): -1,
        ("A", "F"): -2,
        ("A", "P"): -1,
        ("A", "S"): 1,
        ("A", "T"): 0,
        ("A", "W"): -3,
        ("A", "Y"): -2,
        ("A", "V"): 0,
        ("R", "R"): 5,
        ("R", "N"): 0,
        ("R", "D"): -2,
        ("R", "C"): -3,
        ("R", "Q"): 1,
        ("R", "E"): 0,
        ("R", "G"): -2,
        ("R", "H"): 0,
        ("R", "I"): -3,
        ("R", "L"): -2,
        ("R", "K"): 2,
        ("R", "M"): -1,
        ("R", "F"): -3,
        ("R", "P"): -2,
        ("R", "S"): -1,
        ("R", "T"): -1,
        ("R", "W"): -3,
        ("R", "Y"): -2,
        ("R", "V"): -3,
        # ... (abbreviated - full matrix would be included)
    }

    def __init__(self, matrix_type: str = "simple"):
        self.matrix_type = matrix_type

        if matrix_type == "blosum62":
            self._matrix = self.BLOSUM62
        elif matrix_type == "simple":
            self._match = 2
            self._mismatch = -1
            self._matrix = None
        elif matrix_type == "dna":
            self._match = 1
            self._mismatch = -1
            self._matrix = None

    def score(self, a: str, b: str) -> int:
        """Get score for aligning two characters."""
        if self._matrix:
            return self._matrix.get(
                (a.upper(), b.upper()), self._matrix.get((b.upper(), a.upper()), -1)
            )
        else:
            return self._match if a.upper() == b.upper() else self._mismatch


class SequenceAligner(ABC):
    """Abstract base class for sequence aligners."""

    def __init__(
        self,
        match: int = 2,
        mismatch: int = -1,
        gap_open: int = -5,
        gap_extend: int = -1,
        scoring_matrix: ScoringMatrix | None = None,
    ):
        self.match = match
        self.mismatch = mismatch
        self.gap_open = gap_open
        self.gap_extend = gap_extend
        self.scoring_matrix = scoring_matrix or ScoringMatrix("simple")

    @abstractmethod
    def align(self, seq1: str, seq2: str) -> AlignmentResult:
        """Align two sequences."""
        pass

    def _calculate_identity(self, aligned1: str, aligned2: str) -> tuple[float, int, int]:
        """Calculate identity, gaps, and mismatches."""
        matches = 0
        gaps = 0
        mismatches = 0

        for a, b in zip(aligned1, aligned2, strict=False):
            if a == "-" or b == "-":
                gaps += 1
            elif a == b:
                matches += 1
            else:
                mismatches += 1

        total = len(aligned1)
        identity = matches / total if total > 0 else 0

        return identity, gaps, mismatches


class GlobalAligner(SequenceAligner):
    """Needleman-Wunsch global alignment."""

    def align(self, seq1: str, seq2: str) -> AlignmentResult:
        """Perform global alignment using Needleman-Wunsch algorithm."""
        m, n = len(seq1), len(seq2)

        # Initialize scoring matrix
        dp = np.zeros((m + 1, n + 1))

        # Initialize first row and column with gap penalties
        for i in range(m + 1):
            dp[i, 0] = self.gap_open + i * self.gap_extend if i > 0 else 0
        for j in range(n + 1):
            dp[0, j] = self.gap_open + j * self.gap_extend if j > 0 else 0

        # Fill matrix
        for i in range(1, m + 1):
            for j in range(1, n + 1):
                match_score = self.scoring_matrix.score(seq1[i - 1], seq2[j - 1])

                match = dp[i - 1, j - 1] + match_score
                delete = dp[i - 1, j] + self.gap_extend
                insert = dp[i, j - 1] + self.gap_extend

                dp[i, j] = max(match, delete, insert)

        # Traceback
        aligned1, aligned2 = [], []
        i, j = m, n

        while i > 0 or j > 0:
            if i > 0 and j > 0:
                match_score = self.scoring_matrix.score(seq1[i - 1], seq2[j - 1])
                if dp[i, j] == dp[i - 1, j - 1] + match_score:
                    aligned1.append(seq1[i - 1])
                    aligned2.append(seq2[j - 1])
                    i -= 1
                    j -= 1
                    continue

            if i > 0 and dp[i, j] == dp[i - 1, j] + self.gap_extend:
                aligned1.append(seq1[i - 1])
                aligned2.append("-")
                i -= 1
            else:
                aligned1.append("-")
                aligned2.append(seq2[j - 1])
                j -= 1

        aligned1 = "".join(reversed(aligned1))
        aligned2 = "".join(reversed(aligned2))

        identity, gaps, mismatches = self._calculate_identity(aligned1, aligned2)

        return AlignmentResult(
            seq1_aligned=aligned1,
            seq2_aligned=aligned2,
            score=dp[m, n],
            identity=identity,
            gaps=gaps,
            mismatches=mismatches,
            alignment_length=len(aligned1),
            start1=0,
            end1=m,
            start2=0,
            end2=n,
        )


class LocalAligner(SequenceAligner):
    """Smith-Waterman local alignment."""

    def align(self, seq1: str, seq2: str) -> AlignmentResult:
        """Perform local alignment using Smith-Waterman algorithm."""
        m, n = len(seq1), len(seq2)

        # Initialize scoring matrix
        dp = np.zeros((m + 1, n + 1))

        max_score = 0
        max_pos = (0, 0)

        # Fill matrix
        for i in range(1, m + 1):
            for j in range(1, n + 1):
                match_score = self.scoring_matrix.score(seq1[i - 1], seq2[j - 1])

                match = dp[i - 1, j - 1] + match_score
                delete = dp[i - 1, j] + self.gap_extend
                insert = dp[i, j - 1] + self.gap_extend

                dp[i, j] = max(0, match, delete, insert)

                if dp[i, j] > max_score:
                    max_score = dp[i, j]
                    max_pos = (i, j)

        # Traceback from max score
        aligned1, aligned2 = [], []
        i, j = max_pos
        end1, end2 = i, j

        while i > 0 and j > 0 and dp[i, j] > 0:
            match_score = self.scoring_matrix.score(seq1[i - 1], seq2[j - 1])

            if dp[i, j] == dp[i - 1, j - 1] + match_score:
                aligned1.append(seq1[i - 1])
                aligned2.append(seq2[j - 1])
                i -= 1
                j -= 1
            elif dp[i, j] == dp[i - 1, j] + self.gap_extend:
                aligned1.append(seq1[i - 1])
                aligned2.append("-")
                i -= 1
            else:
                aligned1.append("-")
                aligned2.append(seq2[j - 1])
                j -= 1

        start1, start2 = i, j
        aligned1 = "".join(reversed(aligned1))
        aligned2 = "".join(reversed(aligned2))

        identity, gaps, mismatches = self._calculate_identity(aligned1, aligned2)

        return AlignmentResult(
            seq1_aligned=aligned1,
            seq2_aligned=aligned2,
            score=max_score,
            identity=identity,
            gaps=gaps,
            mismatches=mismatches,
            alignment_length=len(aligned1),
            start1=start1,
            end1=end1,
            start2=start2,
            end2=end2,
        )


class MultipleSequenceAligner:
    """Multiple sequence alignment using progressive alignment."""

    def __init__(self, gap_penalty: float = -1.0):
        self.gap_penalty = gap_penalty
        self.pairwise_aligner = GlobalAligner()

    def align(self, sequences: list[str]) -> list[str]:
        """Align multiple sequences using progressive alignment."""
        if len(sequences) < 2:
            return sequences

        # Calculate pairwise distances
        n = len(sequences)
        distances = np.zeros((n, n))

        for i in range(n):
            for j in range(i + 1, n):
                result = self.pairwise_aligner.align(sequences[i], sequences[j])
                distances[i, j] = 1 - result.identity
                distances[j, i] = distances[i, j]

        # Build guide tree using UPGMA
        tree = self._upgma(distances)

        # Progressive alignment following guide tree
        aligned = self._progressive_align(sequences, tree)

        return aligned

    def _upgma(self, distances: np.ndarray) -> list:
        """Build UPGMA guide tree."""
        n = distances.shape[0]
        clusters = [[i] for i in range(n)]
        heights = [0.0] * n

        while len(clusters) > 1:
            # Find minimum distance
            min_dist = float("inf")
            min_i, min_j = 0, 1

            for i in range(len(clusters)):
                for j in range(i + 1, len(clusters)):
                    dist = self._cluster_distance(clusters[i], clusters[j], distances)
                    if dist < min_dist:
                        min_dist = dist
                        min_i, min_j = i, j

            # Merge clusters
            new_cluster = clusters[min_i] + clusters[min_j]
            new_height = min_dist / 2

            clusters = [c for k, c in enumerate(clusters) if k not in [min_i, min_j]]
            clusters.append(new_cluster)
            heights = [h for k, h in enumerate(heights) if k not in [min_i, min_j]]
            heights.append(new_height)

        return clusters[0]

    def _cluster_distance(self, c1: list, c2: list, distances: np.ndarray) -> float:
        """Calculate average distance between clusters."""
        total = 0.0
        count = 0
        for i in c1:
            for j in c2:
                total += distances[i, j]
                count += 1
        return total / count if count > 0 else 0.0

    def _progressive_align(self, sequences: list[str], tree: list) -> list[str]:
        """Perform progressive alignment following guide tree."""
        # Simplified: just align sequences in tree order
        aligned = [sequences[tree[0]]]

        for idx in tree[1:]:
            # Align new sequence to profile
            new_seq = sequences[idx]

            # Use first aligned sequence as reference (simplified)
            result = self.pairwise_aligner.align(aligned[0], new_seq)

            # Update all aligned sequences with new gaps
            aligned = [self._add_gaps(seq, result.seq1_aligned, aligned[0]) for seq in aligned]
            aligned.append(result.seq2_aligned)

        return aligned

    def _add_gaps(self, seq: str, template: str, original: str) -> str:
        """Add gaps to sequence based on template alignment."""
        result = []
        seq_idx = 0

        for _i, char in enumerate(template):
            if char == "-":
                result.append("-")
            else:
                if seq_idx < len(seq):
                    result.append(seq[seq_idx])
                    seq_idx += 1

        return "".join(result)


class MotifFinder:
    """Find sequence motifs using various algorithms."""

    def __init__(self, alphabet: str = "ACGT"):
        self.alphabet = alphabet

    def find_exact_motifs(
        self,
        sequences: list[str],
        motif_length: int,
        min_occurrences: int = 2,
    ) -> list[tuple[str, int]]:
        """Find exact motifs that appear in multiple sequences."""
        motif_counts = defaultdict(int)

        for seq in sequences:
            seen = set()
            for i in range(len(seq) - motif_length + 1):
                motif = seq[i : i + motif_length]
                if motif not in seen:
                    motif_counts[motif] += 1
                    seen.add(motif)

        motifs = [(m, c) for m, c in motif_counts.items() if c >= min_occurrences]
        return sorted(motifs, key=lambda x: -x[1])

    def find_consensus_motif(
        self,
        sequences: list[str],
        motif_length: int,
    ) -> tuple[str, np.ndarray]:
        """Find consensus motif using position weight matrix."""
        # Initialize position frequency matrix
        pfm = np.zeros((len(self.alphabet), motif_length))

        # Count frequencies at each position
        for seq in sequences:
            for i in range(len(seq) - motif_length + 1):
                for j, base in enumerate(seq[i : i + motif_length]):
                    if base in self.alphabet:
                        idx = self.alphabet.index(base)
                        pfm[idx, j] += 1

        # Convert to position weight matrix
        total = pfm.sum(axis=0, keepdims=True)
        pwm = (pfm + 1) / (total + len(self.alphabet))  # Add pseudocount
        pwm = np.log2(pwm / (1 / len(self.alphabet)))

        # Get consensus
        consensus = ""
        for j in range(motif_length):
            max_idx = np.argmax(pfm[:, j])
            consensus += self.alphabet[max_idx]

        return consensus, pwm

    def score_motif(self, sequence: str, pwm: np.ndarray) -> float:
        """Score a sequence against a PWM."""
        score = 0.0
        for i, base in enumerate(sequence):
            if base in self.alphabet and i < pwm.shape[1]:
                idx = self.alphabet.index(base)
                score += pwm[idx, i]
        return score

    def find_motif_occurrences(
        self,
        sequence: str,
        pwm: np.ndarray,
        threshold: float = 0.0,
    ) -> list[tuple[int, float]]:
        """Find motif occurrences above threshold."""
        motif_length = pwm.shape[1]
        occurrences = []

        for i in range(len(sequence) - motif_length + 1):
            subseq = sequence[i : i + motif_length]
            score = self.score_motif(subseq, pwm)
            if score >= threshold:
                occurrences.append((i, score))

        return sorted(occurrences, key=lambda x: -x[1])


class KmerCounter:
    """K-mer counting and analysis."""

    def __init__(self, k: int = 21, canonical: bool = True):
        self.k = k
        self.canonical = canonical

    def count_kmers(self, sequence: str) -> dict[str, int]:
        """Count k-mers in a sequence."""
        counts = defaultdict(int)

        for i in range(len(sequence) - self.k + 1):
            kmer = sequence[i : i + self.k]

            if "N" in kmer:
                continue

            if self.canonical:
                # Use canonical (lexicographically smaller) k-mer
                revcomp = self._reverse_complement(kmer)
                kmer = min(kmer, revcomp)

            counts[kmer] += 1

        return dict(counts)

    def _reverse_complement(self, kmer: str) -> str:
        """Get reverse complement of k-mer."""
        complement = {"A": "T", "T": "A", "G": "C", "C": "G"}
        return "".join(complement.get(b, "N") for b in reversed(kmer))

    def kmer_frequency(self, sequence: str) -> dict[str, float]:
        """Calculate k-mer frequencies."""
        counts = self.count_kmers(sequence)
        total = sum(counts.values())
        return {k: v / total for k, v in counts.items()} if total > 0 else {}

    def compare_sequences(
        self,
        seq1: str,
        seq2: str,
        method: str = "jaccard",
    ) -> float:
        """Compare sequences using k-mer similarity."""
        kmers1 = set(self.count_kmers(seq1).keys())
        kmers2 = set(self.count_kmers(seq2).keys())

        if method == "jaccard":
            intersection = len(kmers1 & kmers2)
            union = len(kmers1 | kmers2)
            return intersection / union if union > 0 else 0.0

        elif method == "containment":
            intersection = len(kmers1 & kmers2)
            return intersection / len(kmers1) if len(kmers1) > 0 else 0.0

        elif method == "cosine":
            freq1 = self.kmer_frequency(seq1)
            freq2 = self.kmer_frequency(seq2)

            all_kmers = set(freq1.keys()) | set(freq2.keys())

            dot_product = sum(freq1.get(k, 0) * freq2.get(k, 0) for k in all_kmers)
            norm1 = np.sqrt(sum(v**2 for v in freq1.values()))
            norm2 = np.sqrt(sum(v**2 for v in freq2.values()))

            return dot_product / (norm1 * norm2) if norm1 * norm2 > 0 else 0.0

        else:
            raise ValueError(f"Unknown method: {method}")

    def sketch(self, sequence: str, sketch_size: int = 1000) -> list[str]:
        """Create MinHash sketch of sequence."""
        kmers = list(self.count_kmers(sequence).keys())

        # Simple hash-based sketching
        hashed = sorted(kmers, key=lambda x: hash(x))

        return hashed[:sketch_size]

    def estimate_similarity(
        self,
        sketch1: list[str],
        sketch2: list[str],
    ) -> float:
        """Estimate Jaccard similarity from sketches."""
        set1 = set(sketch1)
        set2 = set(sketch2)

        intersection = len(set1 & set2)
        union = len(set1 | set2)

        return intersection / union if union > 0 else 0.0


class BurrowsWheelerTransform:
    """Burrows-Wheeler Transform for sequence indexing."""

    def __init__(self, sequence: str):
        self.original = sequence
        self.bwt, self.suffix_array = self._build_bwt(sequence + "$")

    def _build_bwt(self, text: str) -> tuple[str, list[int]]:
        """Build BWT and suffix array."""
        rotations = sorted(range(len(text)), key=lambda i: text[i:] + text[:i])
        bwt = "".join(text[(i - 1) % len(text)] for i in rotations)
        return bwt, rotations

    def search(self, pattern: str) -> list[int]:
        """Search for pattern using BWT."""
        # Build occurrence table
        occ = defaultdict(list)
        for i, char in enumerate(self.bwt):
            occ[char].append(i)

        # Count occurrences
        counts = {}
        for char in set(self.bwt):
            counts[char] = sum(1 for c in self.bwt if c < char)

        # Search
        top = 0
        bottom = len(self.bwt) - 1

        for char in reversed(pattern):
            if char not in occ:
                return []

            # Find range
            positions = occ[char]
            top_count = sum(1 for p in positions if p < top)
            bottom_count = sum(1 for p in positions if p <= bottom)

            top = counts.get(char, 0) + top_count
            bottom = counts.get(char, 0) + bottom_count - 1

            if top > bottom:
                return []

        # Get positions from suffix array
        return [self.suffix_array[i] for i in range(top, bottom + 1)]


class SuffixArray:
    """Suffix array for efficient pattern matching."""

    def __init__(self, text: str):
        self.text = text
        self.sa = self._build_suffix_array(text)
        self.lcp = self._build_lcp_array()

    def _build_suffix_array(self, text: str) -> list[int]:
        """Build suffix array using simple sorting."""
        return sorted(range(len(text)), key=lambda i: text[i:])

    def _build_lcp_array(self) -> list[int]:
        """Build LCP (Longest Common Prefix) array."""
        n = len(self.text)
        rank = [0] * n

        for i, suffix_idx in enumerate(self.sa):
            rank[suffix_idx] = i

        lcp = [0] * n
        h = 0

        for i in range(n):
            if rank[i] > 0:
                j = self.sa[rank[i] - 1]
                while i + h < n and j + h < n and self.text[i + h] == self.text[j + h]:
                    h += 1
                lcp[rank[i]] = h
                if h > 0:
                    h -= 1

        return lcp

    def search(self, pattern: str) -> list[int]:
        """Binary search for pattern occurrences."""
        n = len(self.text)
        m = len(pattern)

        # Find left boundary
        left = 0
        right = n

        while left < right:
            mid = (left + right) // 2
            suffix = self.text[self.sa[mid] :]
            if suffix < pattern:
                left = mid + 1
            else:
                right = mid

        start = left

        # Find right boundary
        right = n

        while left < right:
            mid = (left + right) // 2
            suffix = self.text[self.sa[mid] : self.sa[mid] + m]
            if suffix <= pattern:
                left = mid + 1
            else:
                right = mid

        return [self.sa[i] for i in range(start, left)]

    def longest_repeated_substring(self) -> str:
        """Find longest repeated substring using LCP array."""
        max_lcp = max(self.lcp) if self.lcp else 0
        max_idx = self.lcp.index(max_lcp) if max_lcp > 0 else 0

        if max_lcp == 0:
            return ""

        return self.text[self.sa[max_idx] : self.sa[max_idx] + max_lcp]

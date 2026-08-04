"""Assembly Polishing Module.
=========================

Tools for polishing and error correction of assembled sequences.
"""

import logging
from collections import Counter, defaultdict
from dataclasses import dataclass, field

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class PolishingResult:
    """Result of assembly polishing."""

    sequence: str
    original_length: int
    polished_length: int
    corrections_made: int
    snp_corrections: int
    insertion_corrections: int
    deletion_corrections: int
    regions_low_confidence: list[tuple[int, int]] = field(default_factory=list)


class ConsensusPolisher:
    """Polish assembly using read consensus."""

    def __init__(
        self,
        min_coverage: int = 3,
        min_consensus_fraction: float = 0.6,
    ):
        self.min_coverage = min_coverage
        self.min_consensus_fraction = min_consensus_fraction

    def polish(
        self,
        sequence: str,
        reads: list[str],
        qualities: list[list[int]] | None = None,
    ) -> PolishingResult:
        """Polish sequence using read consensus."""
        logger.info(f"Polishing sequence of length {len(sequence)}")

        # Map reads to sequence
        pileup = self._build_pileup(sequence, reads, qualities)

        # Call consensus
        polished, corrections = self._call_consensus(sequence, pileup)

        return PolishingResult(
            sequence=polished,
            original_length=len(sequence),
            polished_length=len(polished),
            corrections_made=sum(corrections.values()),
            snp_corrections=corrections["snp"],
            insertion_corrections=corrections["ins"],
            deletion_corrections=corrections["del"],
        )

    def _build_pileup(
        self,
        sequence: str,
        reads: list[str],
        qualities: list[list[int]] | None = None,
    ) -> list[dict[str, int]]:
        """Build pileup from mapped reads."""
        k = 15

        # Build sequence k-mer index
        seq_index: dict[str, list[int]] = defaultdict(list)
        for i in range(len(sequence) - k + 1):
            kmer = sequence[i : i + k]
            if "N" not in kmer:
                seq_index[kmer].append(i)

        # Initialize pileup
        pileup = [defaultdict(int) for _ in range(len(sequence))]

        # Map and add reads to pileup
        for read_idx, read in enumerate(reads):
            read = read.upper()
            quals = qualities[read_idx] if qualities else None

            # Find best mapping position
            matches = defaultdict(int)
            for i in range(len(read) - k + 1):
                kmer = read[i : i + k]
                for pos in seq_index.get(kmer, []):
                    map_pos = pos - i
                    if 0 <= map_pos <= len(sequence) - len(read):
                        matches[map_pos] += 1

            if matches:
                best_pos = max(matches.keys(), key=lambda p: matches[p])

                # Add bases to pileup
                for i, base in enumerate(read):
                    if best_pos + i < len(sequence):
                        quality_weight = 1
                        if quals and i < len(quals):
                            quality_weight = min(quals[i] / 30, 1.0)

                        pileup[best_pos + i][base] += int(10 * quality_weight)

        return pileup

    def _call_consensus(
        self,
        sequence: str,
        pileup: list[dict[str, int]],
    ) -> tuple[str, dict[str, int]]:
        """Call consensus from pileup."""
        consensus = []
        corrections = {"snp": 0, "ins": 0, "del": 0}

        for i, pile in enumerate(pileup):
            if not pile:
                consensus.append(sequence[i])
                continue

            total = sum(pile.values())

            if total < self.min_coverage:
                consensus.append(sequence[i])
                continue

            # Find consensus base
            best_base = max(pile.keys(), key=lambda b: pile[b])
            best_fraction = pile[best_base] / total

            if best_fraction >= self.min_consensus_fraction:
                if best_base != sequence[i]:
                    corrections["snp"] += 1
                consensus.append(best_base)
            else:
                consensus.append(sequence[i])

        return "".join(consensus), corrections

    def polish_with_long_reads(
        self,
        sequence: str,
        long_reads: list[str],
        iterations: int = 2,
    ) -> PolishingResult:
        """Polish sequence using long reads with multiple iterations."""
        current = sequence
        total_corrections = {"snp": 0, "ins": 0, "del": 0}

        for iteration in range(iterations):
            logger.info(f"Polishing iteration {iteration + 1}/{iterations}")

            result = self.polish(current, long_reads)
            current = result.sequence

            total_corrections["snp"] += result.snp_corrections
            total_corrections["ins"] += result.insertion_corrections
            total_corrections["del"] += result.deletion_corrections

            if result.corrections_made == 0:
                break

        return PolishingResult(
            sequence=current,
            original_length=len(sequence),
            polished_length=len(current),
            corrections_made=sum(total_corrections.values()),
            snp_corrections=total_corrections["snp"],
            insertion_corrections=total_corrections["ins"],
            deletion_corrections=total_corrections["del"],
        )


class ErrorCorrector:
    """Correct errors in sequences using k-mer based methods."""

    def __init__(
        self,
        k: int = 21,
        min_kmer_count: int = 3,
        trusted_cutoff: int = 10,
    ):
        self.k = k
        self.min_kmer_count = min_kmer_count
        self.trusted_cutoff = trusted_cutoff
        self.kmer_counts: dict[str, int] = {}

    def build_kmer_spectrum(self, reads: list[str]):
        """Build k-mer spectrum from reads."""
        logger.info("Building k-mer spectrum")

        self.kmer_counts = defaultdict(int)

        for read in reads:
            read = read.upper()
            for i in range(len(read) - self.k + 1):
                kmer = read[i : i + self.k]
                if "N" not in kmer:
                    # Use canonical k-mer
                    revcomp = self._reverse_complement(kmer)
                    canonical = min(kmer, revcomp)
                    self.kmer_counts[canonical] += 1

        logger.info(f"Built spectrum with {len(self.kmer_counts)} unique k-mers")

    def _reverse_complement(self, seq: str) -> str:
        """Get reverse complement."""
        complement = {"A": "T", "T": "A", "G": "C", "C": "G", "N": "N"}
        return "".join(complement.get(b, "N") for b in reversed(seq))

    def correct_read(self, read: str) -> tuple[str, int]:
        """Correct errors in a single read."""
        read = read.upper()
        corrections = 0
        corrected = list(read)

        i = 0
        while i <= len(read) - self.k:
            kmer = "".join(corrected[i : i + self.k])

            if "N" in kmer:
                i += 1
                continue

            canonical = min(kmer, self._reverse_complement(kmer))
            count = self.kmer_counts.get(canonical, 0)

            if count < self.min_kmer_count:
                # Try to correct
                best_correction = None
                best_count = count

                # Try single-base substitutions
                for pos in range(self.k):
                    for base in "ACGT":
                        if base != kmer[pos]:
                            new_kmer = kmer[:pos] + base + kmer[pos + 1 :]
                            new_canonical = min(new_kmer, self._reverse_complement(new_kmer))
                            new_count = self.kmer_counts.get(new_canonical, 0)

                            if new_count > best_count and new_count >= self.trusted_cutoff:
                                best_count = new_count
                                best_correction = (i + pos, base)

                if best_correction:
                    corrected[best_correction[0]] = best_correction[1]
                    corrections += 1
                    continue

            i += 1

        return "".join(corrected), corrections

    def correct_reads(self, reads: list[str]) -> tuple[list[str], int]:
        """Correct errors in multiple reads."""
        logger.info(f"Correcting {len(reads)} reads")

        corrected_reads = []
        total_corrections = 0

        for read in reads:
            corrected, corrections = self.correct_read(read)
            corrected_reads.append(corrected)
            total_corrections += corrections

        logger.info(f"Made {total_corrections} corrections")
        return corrected_reads, total_corrections

    def correct_assembly(self, sequence: str) -> tuple[str, int]:
        """Correct errors in assembly using k-mer spectrum."""
        return self.correct_read(sequence)


class HomopolymerCorrector:
    """Correct homopolymer errors common in long-read sequencing."""

    def __init__(
        self,
        min_homopolymer_length: int = 3,
        max_correction: int = 2,
    ):
        self.min_homopolymer_length = min_homopolymer_length
        self.max_correction = max_correction

    def correct(
        self,
        sequence: str,
        reads: list[str],
    ) -> tuple[str, int]:
        """Correct homopolymer errors using read evidence."""
        logger.info("Correcting homopolymer errors")

        # Find homopolymer regions
        homopolymers = self._find_homopolymers(sequence)

        # Build pileup around homopolymers
        corrections = []

        for start, end, base in homopolymers:
            true_length = self._estimate_true_length(
                sequence,
                start,
                end,
                base,
                reads,
            )

            current_length = end - start
            if true_length != current_length:
                diff = true_length - current_length
                if abs(diff) <= self.max_correction:
                    corrections.append((start, end, base, true_length))

        # Apply corrections
        corrected = self._apply_corrections(sequence, corrections)

        return corrected, len(corrections)

    def _find_homopolymers(
        self,
        sequence: str,
    ) -> list[tuple[int, int, str]]:
        """Find homopolymer regions in sequence."""
        homopolymers = []

        i = 0
        while i < len(sequence):
            base = sequence[i]
            j = i + 1

            while j < len(sequence) and sequence[j] == base:
                j += 1

            length = j - i
            if length >= self.min_homopolymer_length:
                homopolymers.append((i, j, base))

            i = j

        return homopolymers

    def _estimate_true_length(
        self,
        sequence: str,
        start: int,
        end: int,
        base: str,
        reads: list[str],
    ) -> int:
        """Estimate true homopolymer length from reads."""
        # Get flanking sequence
        flank_size = 15
        left_flank = sequence[max(0, start - flank_size) : start]
        right_flank = sequence[end : end + flank_size]

        observed_lengths = []

        for read in reads:
            read = read.upper()

            # Find read position matching flanks
            left_pos = read.find(left_flank)

            if left_pos != -1:
                hp_start = left_pos + len(left_flank)

                # Count homopolymer length in read
                hp_length = 0
                while hp_start + hp_length < len(read) and read[hp_start + hp_length] == base:
                    hp_length += 1

                if hp_length > 0:
                    # Verify right flank
                    if hp_start + hp_length + len(right_flank) <= len(read):
                        if (
                            read[hp_start + hp_length : hp_start + hp_length + len(right_flank)]
                            == right_flank
                        ):
                            observed_lengths.append(hp_length)

        if observed_lengths:
            # Return median length
            return int(np.median(observed_lengths))

        return end - start  # Return original length if no evidence

    def _apply_corrections(
        self,
        sequence: str,
        corrections: list[tuple[int, int, str, int]],
    ) -> str:
        """Apply homopolymer corrections to sequence."""
        # Sort corrections by position (reverse order for correct indexing)
        corrections = sorted(corrections, key=lambda x: -x[0])

        result = list(sequence)

        for start, end, base, true_length in corrections:
            current_length = end - start

            if true_length > current_length:
                # Insert bases
                result[start:end] = [base] * true_length
            else:
                # Remove bases
                result[start:end] = [base] * true_length

        return "".join(result)


class Racon:
    """Racon-like consensus polishing."""

    def __init__(
        self,
        window_size: int = 500,
        quality_threshold: int = 10,
    ):
        self.window_size = window_size
        self.quality_threshold = quality_threshold

    def polish(
        self,
        sequence: str,
        alignments: list[dict],
    ) -> str:
        """Polish sequence using POA-like consensus."""
        # Build windowed consensus
        windows = []

        for start in range(0, len(sequence), self.window_size // 2):
            end = min(start + self.window_size, len(sequence))

            # Get alignments overlapping window
            window_alns = [a for a in alignments if a["ref_start"] < end and a["ref_end"] > start]

            if window_alns:
                consensus = self._window_consensus(
                    sequence[start:end],
                    window_alns,
                    start,
                )
                windows.append((start, end, consensus))

        # Merge windows
        return self._merge_windows(sequence, windows)

    def _window_consensus(
        self,
        window_seq: str,
        alignments: list[dict],
        window_start: int,
    ) -> str:
        """Build consensus for a window."""
        # Simple majority voting
        pileup = [Counter() for _ in range(len(window_seq))]

        for aln in alignments:
            # Extract aligned portion
            for i, (ref_pos, query_base) in enumerate(aln.get("aligned_pairs", [])):
                if ref_pos is not None and query_base is not None:
                    local_pos = ref_pos - window_start
                    if 0 <= local_pos < len(window_seq):
                        pileup[local_pos][query_base] += 1

        # Call consensus
        consensus = []
        for i, pile in enumerate(pileup):
            if pile:
                best_base = pile.most_common(1)[0][0]
                consensus.append(best_base)
            else:
                consensus.append(window_seq[i])

        return "".join(consensus)

    def _merge_windows(
        self,
        sequence: str,
        windows: list[tuple[int, int, str]],
    ) -> str:
        """Merge overlapping consensus windows."""
        if not windows:
            return sequence

        result = list(sequence)

        for start, _end, consensus in windows:
            for i, base in enumerate(consensus):
                if start + i < len(result):
                    result[start + i] = base

        return "".join(result)


class Medaka:
    """Medaka-like neural network polishing interface."""

    def __init__(self, model_path: str | None = None):
        self.model_path = model_path
        self.model = None

    def load_model(self) -> None:
        """Optional ONNX/Torch weights hook.

        Bundled releases omit large model weights; when ``model_path`` points to a
        supported checkpoint, wire your loader here. Until then, :meth:`polish`
        delegates to :class:`ConsensusPolisher`.
        """
        if self.model_path:
            logger.info("Medaka model_path set (%s); custom loader not bundled", self.model_path)
        else:
            logger.info("Medaka neural weights not configured; using consensus polisher")

    def polish(
        self,
        sequence: str,
        reads: list[str],
        batch_size: int = 100,
    ) -> str:
        """Polish sequence; neural path is unconfigured, so consensus polishing is used."""
        logger.info("Polishing with consensus backend (Medaka NN optional)")
        polisher = ConsensusPolisher()
        result = polisher.polish(sequence, reads)

        return result.sequence

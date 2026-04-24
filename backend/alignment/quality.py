"""Alignment Quality Module.
========================

Quality control and statistics for alignments.
"""

import logging
from collections import defaultdict
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class MappingStatistics:
    """Mapping statistics summary."""

    total_reads: int = 0
    mapped_reads: int = 0
    unmapped_reads: int = 0
    paired_reads: int = 0
    properly_paired: int = 0
    singleton_reads: int = 0

    secondary_alignments: int = 0
    supplementary_alignments: int = 0
    duplicate_reads: int = 0

    forward_reads: int = 0
    reverse_reads: int = 0

    total_bases: int = 0
    mapped_bases: int = 0

    mean_mapping_quality: float = 0.0
    mean_read_length: float = 0.0

    @property
    def mapping_rate(self) -> float:
        return self.mapped_reads / self.total_reads if self.total_reads > 0 else 0.0

    @property
    def proper_pair_rate(self) -> float:
        return self.properly_paired / self.paired_reads if self.paired_reads > 0 else 0.0

    @property
    def duplicate_rate(self) -> float:
        return self.duplicate_reads / self.total_reads if self.total_reads > 0 else 0.0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "total_reads": self.total_reads,
            "mapped_reads": self.mapped_reads,
            "unmapped_reads": self.unmapped_reads,
            "mapping_rate": f"{self.mapping_rate:.2%}",
            "paired_reads": self.paired_reads,
            "properly_paired": self.properly_paired,
            "proper_pair_rate": f"{self.proper_pair_rate:.2%}",
            "singleton_reads": self.singleton_reads,
            "secondary_alignments": self.secondary_alignments,
            "supplementary_alignments": self.supplementary_alignments,
            "duplicate_reads": self.duplicate_reads,
            "duplicate_rate": f"{self.duplicate_rate:.2%}",
            "forward_reads": self.forward_reads,
            "reverse_reads": self.reverse_reads,
            "total_bases": self.total_bases,
            "mapped_bases": self.mapped_bases,
            "mean_mapping_quality": f"{self.mean_mapping_quality:.1f}",
            "mean_read_length": f"{self.mean_read_length:.0f}",
        }


class AlignmentQC:
    """Alignment quality control."""

    def __init__(self):
        self.quality_histogram = defaultdict(int)
        self.read_lengths = []
        self.insert_sizes = []

    def calculate_statistics(
        self,
        alignments: list["AlignmentResult"],
    ) -> MappingStatistics:
        """Calculate mapping statistics."""
        stats = MappingStatistics()

        mapping_qualities = []

        for aln in alignments:
            stats.total_reads += 1
            stats.total_bases += len(aln.query_sequence)
            self.read_lengths.append(len(aln.query_sequence))

            if aln.is_mapped:
                stats.mapped_reads += 1
                stats.mapped_bases += len(aln.query_sequence)
                mapping_qualities.append(aln.mapping_quality)
                self.quality_histogram[aln.mapping_quality] += 1

                if aln.is_reverse:
                    stats.reverse_reads += 1
                else:
                    stats.forward_reads += 1
            else:
                stats.unmapped_reads += 1

            if aln.is_paired:
                stats.paired_reads += 1

                if aln.template_length != 0:
                    self.insert_sizes.append(abs(aln.template_length))

            if aln.is_secondary:
                stats.secondary_alignments += 1

            if aln.is_supplementary:
                stats.supplementary_alignments += 1

        if mapping_qualities:
            stats.mean_mapping_quality = np.mean(mapping_qualities)

        if self.read_lengths:
            stats.mean_read_length = np.mean(self.read_lengths)

        return stats

    def get_quality_distribution(self) -> dict[int, int]:
        """Get mapping quality distribution."""
        return dict(self.quality_histogram)

    def get_read_length_distribution(self) -> dict:
        """Get read length distribution statistics."""
        if not self.read_lengths:
            return {}

        return {
            "min": min(self.read_lengths),
            "max": max(self.read_lengths),
            "mean": np.mean(self.read_lengths),
            "median": np.median(self.read_lengths),
            "std": np.std(self.read_lengths),
        }


class InsertSizeDistribution:
    """Analyze insert size distribution for paired-end data."""

    def __init__(self):
        self.insert_sizes = []

    def collect(self, alignments: list["AlignmentResult"]):
        """Collect insert sizes from alignments."""
        for aln in alignments:
            if aln.is_paired and aln.is_mapped and aln.template_length != 0:
                self.insert_sizes.append(abs(aln.template_length))

    def calculate_statistics(self) -> dict:
        """Calculate insert size statistics."""
        if not self.insert_sizes:
            return {}

        sizes = np.array(self.insert_sizes)

        # Remove outliers for mean/std calculation
        q25, q75 = np.percentile(sizes, [25, 75])
        iqr = q75 - q25
        lower = q25 - 1.5 * iqr
        upper = q75 + 1.5 * iqr
        filtered = sizes[(sizes >= lower) & (sizes <= upper)]

        return {
            "count": len(self.insert_sizes),
            "min": int(np.min(sizes)),
            "max": int(np.max(sizes)),
            "mean": float(np.mean(filtered)),
            "median": float(np.median(sizes)),
            "std": float(np.std(filtered)),
            "q25": float(q25),
            "q75": float(q75),
            "mode": int(np.bincount(sizes.astype(int)).argmax()),
        }

    def histogram(self, bins: int = 100) -> tuple[np.ndarray, np.ndarray]:
        """Generate histogram of insert sizes."""
        if not self.insert_sizes:
            return np.array([]), np.array([])

        sizes = np.array(self.insert_sizes)
        counts, edges = np.histogram(sizes, bins=bins)

        return counts, edges


class CoverageAnalysis:
    """Analyze coverage distribution."""

    def __init__(self):
        self.coverage_by_position = {}

    def calculate_coverage(
        self,
        alignments: list["AlignmentResult"],
        reference_lengths: dict[str, int],
    ) -> dict[str, np.ndarray]:
        """Calculate per-base coverage for each reference."""
        coverage = {}

        for ref_name, length in reference_lengths.items():
            coverage[ref_name] = np.zeros(length, dtype=np.int32)

        for aln in alignments:
            if not aln.is_mapped:
                continue

            if aln.reference_name in coverage:
                cov_array = coverage[aln.reference_name]
                start = max(0, aln.reference_start)
                end = min(len(cov_array), aln.reference_end)
                cov_array[start:end] += 1

        self.coverage_by_position = coverage
        return coverage

    def get_summary(self) -> dict:
        """Get coverage summary statistics."""
        if not self.coverage_by_position:
            return {}

        all_coverage = np.concatenate(list(self.coverage_by_position.values()))

        return {
            "total_bases": len(all_coverage),
            "covered_bases": int(np.sum(all_coverage > 0)),
            "coverage_breadth": float(np.mean(all_coverage > 0)),
            "mean_depth": float(np.mean(all_coverage)),
            "median_depth": float(np.median(all_coverage)),
            "std_depth": float(np.std(all_coverage)),
            "max_depth": int(np.max(all_coverage)),
            "min_depth": int(np.min(all_coverage)),
            "bases_at_1x": int(np.sum(all_coverage >= 1)),
            "bases_at_10x": int(np.sum(all_coverage >= 10)),
            "bases_at_30x": int(np.sum(all_coverage >= 30)),
            "bases_at_100x": int(np.sum(all_coverage >= 100)),
        }

    def find_gaps(
        self,
        reference_name: str,
        min_coverage: int = 1,
        min_gap_length: int = 100,
    ) -> list[tuple[int, int]]:
        """Find coverage gaps."""
        if reference_name not in self.coverage_by_position:
            return []

        coverage = self.coverage_by_position[reference_name]
        gaps = []

        in_gap = False
        gap_start = 0

        for i, cov in enumerate(coverage):
            if cov < min_coverage:
                if not in_gap:
                    in_gap = True
                    gap_start = i
            else:
                if in_gap:
                    gap_length = i - gap_start
                    if gap_length >= min_gap_length:
                        gaps.append((gap_start, i))
                    in_gap = False

        # Check if we're still in a gap at the end
        if in_gap:
            gap_length = len(coverage) - gap_start
            if gap_length >= min_gap_length:
                gaps.append((gap_start, len(coverage)))

        return gaps

    def gc_coverage_correlation(
        self,
        reference: str,
        window_size: int = 1000,
    ) -> dict:
        """Calculate correlation between GC content and coverage."""
        if not self.coverage_by_position:
            return {}

        for _ref_name, _cov_array in self.coverage_by_position.items():
            # Would need reference sequence
            # Simplified - return empty
            pass

        return {
            "correlation": 0.0,
            "gc_bias": "unknown",
        }

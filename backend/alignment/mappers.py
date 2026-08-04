"""Read Alignment Mappers.
======================

Short and long read alignment algorithms.
"""

import logging
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class AlignmentResult:
    """Result of read alignment."""

    query_name: str
    reference_name: str
    reference_start: int  # 0-based
    mapping_quality: int
    cigar: str
    query_sequence: str
    query_qualities: str | None = None

    # Alignment details
    is_mapped: bool = True
    is_reverse: bool = False
    is_secondary: bool = False
    is_supplementary: bool = False

    # Paired-end info
    is_paired: bool = False
    is_read1: bool = True
    mate_reference_name: str = "*"
    mate_position: int = 0
    template_length: int = 0

    # Scores
    alignment_score: int = 0
    edit_distance: int = 0
    num_mismatches: int = 0

    # Tags
    tags: dict = field(default_factory=dict)

    @property
    def reference_end(self) -> int:
        """Calculate reference end position from CIGAR."""
        ref_len = 0
        num = ""

        for char in self.cigar:
            if char.isdigit():
                num += char
            else:
                length = int(num) if num else 0
                if char in "MDN=X":
                    ref_len += length
                num = ""

        return self.reference_start + ref_len

    @property
    def query_length(self) -> int:
        """Get query sequence length."""
        return len(self.query_sequence)

    @property
    def flag(self) -> int:
        """Calculate SAM flag."""
        flag = 0
        if self.is_paired:
            flag |= 0x1
        if not self.is_mapped:
            flag |= 0x4
        if self.is_reverse:
            flag |= 0x10
        if self.is_secondary:
            flag |= 0x100
        if self.is_supplementary:
            flag |= 0x800
        if self.is_read1:
            flag |= 0x40
        else:
            flag |= 0x80
        return flag

    def to_sam(self) -> str:
        """Convert to SAM format line."""
        tags_str = "\t".join(f"{k}:{t}:{v}" for k, (t, v) in self.tags.items())

        return "\t".join(
            [
                self.query_name,
                str(self.flag),
                self.reference_name if self.is_mapped else "*",
                str(self.reference_start + 1) if self.is_mapped else "0",
                str(self.mapping_quality),
                self.cigar if self.is_mapped else "*",
                self.mate_reference_name,
                str(self.mate_position + 1) if self.mate_position else "0",
                str(self.template_length),
                self.query_sequence,
                self.query_qualities or "*",
                tags_str,
            ]
        )


class Aligner(ABC):
    """Abstract base class for read aligners."""

    def __init__(
        self,
        match_score: int = 1,
        mismatch_penalty: int = -4,
        gap_open: int = -6,
        gap_extend: int = -1,
    ):
        self.match_score = match_score
        self.mismatch_penalty = mismatch_penalty
        self.gap_open = gap_open
        self.gap_extend = gap_extend

    @abstractmethod
    def index(self, reference: str, reference_name: str = "ref"):
        """Build index for reference sequence."""
        pass

    @abstractmethod
    def align(self, query: str, query_name: str = "read") -> list[AlignmentResult]:
        """Align query to indexed reference."""
        pass

    @abstractmethod
    def align_paired(
        self,
        query1: str,
        query2: str,
        query_name: str = "read",
    ) -> tuple[list[AlignmentResult], list[AlignmentResult]]:
        """Align paired-end reads."""
        pass


class BurrowsWheelerAligner(Aligner):
    """BWA-like aligner using FM-index."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.reference = ""
        self.reference_name = ""
        self.suffix_array = []
        self.bwt = ""
        self.occ = {}
        self.c = {}

    def index(self, reference: str, reference_name: str = "ref"):
        """Build FM-index for reference."""
        logger.info(f"Building FM-index for {len(reference)} bp reference")

        self.reference = reference.upper()
        self.reference_name = reference_name

        # Build suffix array
        text = self.reference + "$"
        self.suffix_array = self._build_suffix_array(text)

        # Build BWT
        self.bwt = "".join(text[(i - 1) % len(text)] for i in self.suffix_array)

        # Build occurrence table
        self._build_occurrence_table()

        logger.info("FM-index built successfully")

    def _build_suffix_array(self, text: str) -> list[int]:
        """Build suffix array."""
        return sorted(range(len(text)), key=lambda i: text[i:])

    def _build_occurrence_table(self):
        """Build occurrence count tables."""
        self.occ = defaultdict(list)
        self.c = {}

        counts = defaultdict(int)

        for _i, char in enumerate(self.bwt):
            for c in set(self.bwt):
                self.occ[c].append(counts[c])
            counts[char] += 1

        # C array - count of characters less than each character
        total = 0
        for char in sorted(set(self.bwt)):
            self.c[char] = total
            total += self.bwt.count(char)

    def align(self, query: str, query_name: str = "read") -> list[AlignmentResult]:
        """Align query using FM-index."""
        query = query.upper()

        # Try exact match first
        positions = self._exact_match(query)

        if positions:
            results = []
            for pos in positions[:10]:  # Limit to 10 hits
                results.append(self._create_alignment(query_name, query, pos, is_exact=True))
            return results

        # Try with mismatches
        positions = self._inexact_match(query, max_mismatches=2)

        if positions:
            results = []
            for pos, mismatches in positions[:10]:
                results.append(
                    self._create_alignment(query_name, query, pos, mismatches=mismatches)
                )
            return results

        # Return unmapped
        return [
            AlignmentResult(
                query_name=query_name,
                reference_name="*",
                reference_start=0,
                mapping_quality=0,
                cigar="*",
                query_sequence=query,
                is_mapped=False,
            )
        ]

    def _exact_match(self, pattern: str) -> list[int]:
        """Find exact matches using FM-index."""
        if not self.bwt:
            return []

        top = 0
        bottom = len(self.bwt) - 1

        for char in reversed(pattern):
            if char not in self.c:
                return []

            top = self.c[char] + (self.occ[char][top] if top > 0 else 0)
            bottom = self.c[char] + (
                self.occ[char][bottom] if bottom < len(self.occ[char]) else self.occ[char][-1]
            )

            if top > bottom:
                return []

        return [self.suffix_array[i] for i in range(top, bottom + 1)]

    def _inexact_match(
        self,
        pattern: str,
        max_mismatches: int = 2,
    ) -> list[tuple[int, int]]:
        """Find matches with up to max_mismatches mismatches."""
        # Simplified - seed-and-extend approach
        seed_len = len(pattern) // (max_mismatches + 1)

        candidates = []

        for i in range(max_mismatches + 1):
            seed = pattern[i * seed_len : (i + 1) * seed_len]
            seed_positions = self._exact_match(seed)

            for pos in seed_positions:
                # Extend seed
                ref_start = pos - i * seed_len

                if 0 <= ref_start <= len(self.reference) - len(pattern):
                    ref_region = self.reference[ref_start : ref_start + len(pattern)]
                    mismatches = sum(1 for a, b in zip(pattern, ref_region, strict=False) if a != b)

                    if mismatches <= max_mismatches:
                        candidates.append((ref_start, mismatches))

        # Remove duplicates and sort by mismatches
        seen = set()
        unique = []
        for pos, mm in sorted(candidates, key=lambda x: x[1]):
            if pos not in seen:
                seen.add(pos)
                unique.append((pos, mm))

        return unique

    def _create_alignment(
        self,
        query_name: str,
        query: str,
        position: int,
        is_exact: bool = False,
        mismatches: int = 0,
    ) -> AlignmentResult:
        """Create AlignmentResult from position."""
        cigar = f"{len(query)}M"
        mapq = 60 if is_exact else max(0, 60 - mismatches * 10)

        return AlignmentResult(
            query_name=query_name,
            reference_name=self.reference_name,
            reference_start=position,
            mapping_quality=mapq,
            cigar=cigar,
            query_sequence=query,
            is_mapped=True,
            edit_distance=mismatches,
            num_mismatches=mismatches,
            tags={"NM": ("i", mismatches)},
        )

    def align_paired(
        self,
        query1: str,
        query2: str,
        query_name: str = "read",
        min_insert: int = 100,
        max_insert: int = 1000,
    ) -> tuple[list[AlignmentResult], list[AlignmentResult]]:
        """Align paired-end reads."""
        results1 = self.align(query1, query_name)
        results2 = self.align(query2, query_name)

        # Find concordant pairs
        best_pair = None
        best_score = float("inf")

        for r1 in results1:
            if not r1.is_mapped:
                continue

            for r2 in results2:
                if not r2.is_mapped:
                    continue

                # Check insert size
                if r1.reference_name == r2.reference_name:
                    insert_size = abs(r2.reference_start - r1.reference_start) + len(query2)

                    if min_insert <= insert_size <= max_insert:
                        score = r1.num_mismatches + r2.num_mismatches

                        if score < best_score:
                            best_score = score
                            best_pair = (r1, r2)

        if best_pair:
            r1, r2 = best_pair

            # Update paired info
            r1.is_paired = True
            r1.is_read1 = True
            r1.mate_reference_name = r2.reference_name
            r1.mate_position = r2.reference_start
            r1.template_length = r2.reference_start - r1.reference_start + len(query2)

            r2.is_paired = True
            r2.is_read1 = False
            r2.is_reverse = True  # R2 typically maps to reverse strand
            r2.mate_reference_name = r1.reference_name
            r2.mate_position = r1.reference_start
            r2.template_length = -r1.template_length

            return [r1], [r2]

        return results1[:1], results2[:1]


class MiniMap2Aligner(Aligner):
    """Minimap2-like aligner for long reads."""

    def __init__(
        self,
        k: int = 15,
        w: int = 10,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.k = k  # k-mer size
        self.w = w  # minimizer window size
        self.reference = ""
        self.reference_name = ""
        self.minimizer_index = {}

    def index(self, reference: str, reference_name: str = "ref"):
        """Build minimizer index."""
        logger.info(f"Building minimizer index for {len(reference)} bp reference")

        self.reference = reference.upper()
        self.reference_name = reference_name

        # Extract minimizers
        self.minimizer_index = self._build_minimizer_index(self.reference)

        logger.info(f"Index built with {len(self.minimizer_index)} minimizers")

    def _build_minimizer_index(self, sequence: str) -> dict[str, list[tuple[int, bool]]]:
        """Build minimizer index."""
        index = defaultdict(list)

        for i in range(len(sequence) - self.k - self.w + 1):
            # Find minimizer in window
            window_kmers = []

            for j in range(self.w):
                kmer = sequence[i + j : i + j + self.k]
                if "N" not in kmer:
                    # Use canonical k-mer
                    revcomp = self._reverse_complement(kmer)
                    canonical = min(kmer, revcomp)
                    is_reverse = canonical == revcomp
                    window_kmers.append((canonical, i + j, is_reverse))

            if window_kmers:
                minimizer = min(window_kmers, key=lambda x: x[0])
                index[minimizer[0]].append((minimizer[1], minimizer[2]))

        return dict(index)

    def _reverse_complement(self, seq: str) -> str:
        """Get reverse complement."""
        complement = {"A": "T", "T": "A", "G": "C", "C": "G", "N": "N"}
        return "".join(complement.get(b, "N") for b in reversed(seq))

    def align(self, query: str, query_name: str = "read") -> list[AlignmentResult]:
        """Align long read using minimizer chaining."""
        query = query.upper()

        # Find minimizer matches
        matches = self._find_matches(query)

        if not matches:
            return [
                AlignmentResult(
                    query_name=query_name,
                    reference_name="*",
                    reference_start=0,
                    mapping_quality=0,
                    cigar="*",
                    query_sequence=query,
                    is_mapped=False,
                )
            ]

        # Chain matches
        chains = self._chain_matches(matches, len(query))

        if not chains:
            return [
                AlignmentResult(
                    query_name=query_name,
                    reference_name="*",
                    reference_start=0,
                    mapping_quality=0,
                    cigar="*",
                    query_sequence=query,
                    is_mapped=False,
                )
            ]

        # Extend best chain to full alignment
        results = []
        for chain in chains[:5]:  # Top 5 chains
            alignment = self._extend_chain(chain, query)
            if alignment:
                results.append(
                    AlignmentResult(
                        query_name=query_name,
                        reference_name=self.reference_name,
                        reference_start=alignment["ref_start"],
                        mapping_quality=alignment["mapq"],
                        cigar=alignment["cigar"],
                        query_sequence=query,
                        is_mapped=True,
                        is_reverse=alignment.get("is_reverse", False),
                        alignment_score=alignment["score"],
                        tags={"NM": ("i", alignment.get("edit_distance", 0))},
                    )
                )

        return (
            results
            if results
            else [
                AlignmentResult(
                    query_name=query_name,
                    reference_name="*",
                    reference_start=0,
                    mapping_quality=0,
                    cigar="*",
                    query_sequence=query,
                    is_mapped=False,
                )
            ]
        )

    def _find_matches(self, query: str) -> list[tuple[int, int, bool]]:
        """Find minimizer matches between query and reference."""
        matches = []

        for i in range(len(query) - self.k - self.w + 1):
            window_kmers = []

            for j in range(self.w):
                kmer = query[i + j : i + j + self.k]
                if "N" not in kmer:
                    revcomp = self._reverse_complement(kmer)
                    canonical = min(kmer, revcomp)
                    is_reverse = canonical == revcomp
                    window_kmers.append((canonical, i + j, is_reverse))

            if window_kmers:
                minimizer = min(window_kmers, key=lambda x: x[0])

                # Look up in index
                if minimizer[0] in self.minimizer_index:
                    for ref_pos, ref_reverse in self.minimizer_index[minimizer[0]]:
                        # Determine strand
                        same_strand = minimizer[2] == ref_reverse
                        matches.append((minimizer[1], ref_pos, same_strand))

        return matches

    def _chain_matches(
        self,
        matches: list[tuple[int, int, bool]],
        query_length: int,
    ) -> list[list[tuple[int, int]]]:
        """Chain co-linear matches."""
        if not matches:
            return []

        # Separate by strand
        forward_matches = [(q, r) for q, r, s in matches if s]
        reverse_matches = [(q, r) for q, r, s in matches if not s]

        chains = []

        for strand_matches in [forward_matches, reverse_matches]:
            if not strand_matches:
                continue

            # Sort by query position
            sorted_matches = sorted(strand_matches, key=lambda x: x[0])

            # Simple chaining - find longest increasing subsequence
            chain = [sorted_matches[0]]

            for match in sorted_matches[1:]:
                # Check if colinear
                if match[1] > chain[-1][1] and match[0] > chain[-1][0]:
                    # Check gap size
                    query_gap = match[0] - chain[-1][0]
                    ref_gap = match[1] - chain[-1][1]

                    if abs(query_gap - ref_gap) < 1000:  # Allow some difference
                        chain.append(match)

            if len(chain) >= 3:
                chains.append(chain)

        # Sort chains by length
        chains.sort(key=lambda c: -len(c))

        return chains

    def _extend_chain(self, chain: list[tuple[int, int]], query: str) -> dict | None:
        """Extend chain to full alignment."""
        if not chain:
            return None

        # Estimate alignment region
        ref_start = chain[0][1]
        ref_end = chain[-1][1] + self.k

        # Extend to full query
        ref_start = max(0, ref_start - chain[0][0])
        ref_end = min(len(self.reference), ref_end + (len(query) - chain[-1][0] - self.k))

        # Calculate CIGAR (simplified)
        ref_len = ref_end - ref_start
        query_len = len(query)

        if abs(ref_len - query_len) < 100:
            cigar = f"{query_len}M"
            edit_distance = 0
        else:
            # Has indels
            if ref_len > query_len:
                diff = ref_len - query_len
                cigar = f"{query_len // 2}M{diff}D{query_len - query_len // 2}M"
            else:
                diff = query_len - ref_len
                cigar = f"{ref_len // 2}M{diff}I{ref_len - ref_len // 2}M"
            edit_distance = abs(ref_len - query_len)

        # Calculate mapping quality
        mapq = min(60, len(chain) * 5)

        return {
            "ref_start": ref_start,
            "cigar": cigar,
            "mapq": mapq,
            "score": len(chain) * 100,
            "edit_distance": edit_distance,
        }

    def align_paired(
        self,
        query1: str,
        query2: str,
        query_name: str = "read",
    ) -> tuple[list[AlignmentResult], list[AlignmentResult]]:
        """Align paired long reads."""
        return self.align(query1, query_name), self.align(query2, query_name)


class ShortReadMapper(BurrowsWheelerAligner):
    """Specialized mapper for short reads (Illumina-style)."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.seed_length = 20

    def align(self, query: str, query_name: str = "read") -> list[AlignmentResult]:
        """Align short read with seed-and-extend."""
        query = query.upper()

        # Use multiple seeds
        seeds = []
        for i in range(0, len(query) - self.seed_length + 1, self.seed_length // 2):
            seed = query[i : i + self.seed_length]
            seed_positions = self._exact_match(seed)

            for pos in seed_positions:
                seeds.append((pos - i, i))  # (ref_position, seed_offset)

        # Cluster seeds and extend best clusters
        clusters = self._cluster_seeds(seeds)

        best_alignment = None
        best_score = float("inf")

        for ref_start, _seed_count in clusters[:5]:
            # Extend alignment
            if 0 <= ref_start <= len(self.reference) - len(query):
                ref_region = self.reference[ref_start : ref_start + len(query)]

                mismatches = sum(1 for a, b in zip(query, ref_region, strict=False) if a != b)

                if mismatches < best_score:
                    best_score = mismatches
                    best_alignment = AlignmentResult(
                        query_name=query_name,
                        reference_name=self.reference_name,
                        reference_start=ref_start,
                        mapping_quality=max(0, 60 - mismatches * 10),
                        cigar=f"{len(query)}M",
                        query_sequence=query,
                        is_mapped=True,
                        num_mismatches=mismatches,
                        edit_distance=mismatches,
                        tags={"NM": ("i", mismatches)},
                    )

        if best_alignment:
            return [best_alignment]

        return super().align(query, query_name)

    def _cluster_seeds(self, seeds: list[tuple[int, int]]) -> list[tuple[int, int]]:
        """Cluster seeds by reference position."""
        if not seeds:
            return []

        position_counts = defaultdict(int)
        for ref_pos, _ in seeds:
            position_counts[ref_pos] += 1

        return sorted(position_counts.items(), key=lambda x: -x[1])


class LongReadMapper(MiniMap2Aligner):
    """Specialized mapper for long reads (ONT/PacBio)."""

    def __init__(self, **kwargs):
        super().__init__(k=15, w=10, **kwargs)


class SplicedAligner(Aligner):
    """Aligner for RNA-seq reads with splice junctions."""

    def __init__(
        self,
        known_junctions: list[tuple[int, int]] | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.known_junctions = known_junctions or []
        self.bwa = BurrowsWheelerAligner(**kwargs)
        self.reference = ""
        self.reference_name = ""

    def index(self, reference: str, reference_name: str = "ref"):
        """Build index for spliced alignment."""
        self.reference = reference.upper()
        self.reference_name = reference_name
        self.bwa.index(reference, reference_name)

        # Find potential splice sites
        self._find_splice_sites()

    def _find_splice_sites(self):
        """Find canonical splice sites in reference."""
        # GT-AG splice sites
        self.donor_sites = []
        self.acceptor_sites = []

        for i in range(len(self.reference) - 1):
            if self.reference[i : i + 2] == "GT":
                self.donor_sites.append(i)
            elif self.reference[i : i + 2] == "AG":
                self.acceptor_sites.append(i)

    def align(self, query: str, query_name: str = "read") -> list[AlignmentResult]:
        """Align RNA-seq read with potential splice junctions."""
        query = query.upper()

        # Try unspliced alignment first
        unspliced = self.bwa.align(query, query_name)

        if unspliced and unspliced[0].is_mapped and unspliced[0].num_mismatches <= 2:
            return unspliced

        # Try spliced alignment
        spliced = self._spliced_align(query, query_name)

        if spliced and spliced[0].is_mapped:
            return spliced

        return unspliced

    def _spliced_align(self, query: str, query_name: str) -> list[AlignmentResult]:
        """Attempt spliced alignment."""
        # Split read into segments
        segment_len = len(query) // 2

        seg1 = query[:segment_len]
        seg2 = query[segment_len:]

        # Map segments independently
        results1 = self.bwa.align(seg1, "seg1")
        results2 = self.bwa.align(seg2, "seg2")

        if not results1 or not results2:
            return []

        # Check for valid splice junction
        for r1 in results1:
            if not r1.is_mapped:
                continue

            for r2 in results2:
                if not r2.is_mapped:
                    continue

                # Check if forms valid junction
                intron_start = r1.reference_end
                intron_end = r2.reference_start

                if 50 < intron_end - intron_start < 500000:  # Valid intron size
                    # Check splice signals
                    if (
                        self.reference[intron_start : intron_start + 2] == "GT"
                        and self.reference[intron_end - 2 : intron_end] == "AG"
                    ):

                        # Valid splice junction found
                        intron_len = intron_end - intron_start
                        cigar = f"{segment_len}M{intron_len}N{len(query) - segment_len}M"

                        return [
                            AlignmentResult(
                                query_name=query_name,
                                reference_name=self.reference_name,
                                reference_start=r1.reference_start,
                                mapping_quality=min(r1.mapping_quality, r2.mapping_quality),
                                cigar=cigar,
                                query_sequence=query,
                                is_mapped=True,
                                tags={
                                    "NM": ("i", r1.num_mismatches + r2.num_mismatches),
                                    "XS": ("A", "+"),  # Splice strand
                                },
                            )
                        ]

        return []

    def align_paired(
        self,
        query1: str,
        query2: str,
        query_name: str = "read",
    ) -> tuple[list[AlignmentResult], list[AlignmentResult]]:
        """Align paired RNA-seq reads."""
        return self.align(query1, query_name), self.align(query2, query_name)

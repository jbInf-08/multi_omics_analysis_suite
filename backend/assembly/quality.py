"""Assembly Quality Assessment Module.
==================================

Tools for evaluating assembly quality including QUAST-like metrics,
BUSCO analysis, and various assembly statistics.
"""

import logging
from collections import defaultdict
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ContigStatistics:
    """Statistics for a single contig or assembly."""

    total_length: int = 0
    num_contigs: int = 0
    largest_contig: int = 0
    shortest_contig: int = 0
    mean_length: float = 0.0
    median_length: float = 0.0
    n50: int = 0
    n75: int = 0
    n90: int = 0
    l50: int = 0
    l75: int = 0
    l90: int = 0
    gc_content: float = 0.0
    n_count: int = 0
    n_percentage: float = 0.0
    gaps_count: int = 0
    gaps_length: int = 0

    @classmethod
    def from_sequences(cls, sequences: list[str]) -> "ContigStatistics":
        """Calculate statistics from sequences."""
        if not sequences:
            return cls()

        lengths = sorted([len(s) for s in sequences], reverse=True)
        total = sum(lengths)

        # Calculate Nx values
        cumsum = 0
        n50, n75, n90 = 0, 0, 0
        l50, l75, l90 = 0, 0, 0

        for i, length in enumerate(lengths):
            cumsum += length
            if cumsum >= total * 0.5 and n50 == 0:
                n50 = length
                l50 = i + 1
            if cumsum >= total * 0.75 and n75 == 0:
                n75 = length
                l75 = i + 1
            if cumsum >= total * 0.9 and n90 == 0:
                n90 = length
                l90 = i + 1

        # GC content and N count
        total_gc = 0
        total_n = 0
        total_gaps = 0
        total_gap_length = 0

        for seq in sequences:
            seq_upper = seq.upper()
            total_gc += seq_upper.count("G") + seq_upper.count("C")
            total_n += seq_upper.count("N")

            # Count gaps (consecutive N's)
            in_gap = False
            for base in seq_upper:
                if base == "N":
                    if not in_gap:
                        total_gaps += 1
                        in_gap = True
                    total_gap_length += 1
                else:
                    in_gap = False

        return cls(
            total_length=total,
            num_contigs=len(sequences),
            largest_contig=lengths[0],
            shortest_contig=lengths[-1],
            mean_length=total / len(sequences),
            median_length=lengths[len(lengths) // 2],
            n50=n50,
            n75=n75,
            n90=n90,
            l50=l50,
            l75=l75,
            l90=l90,
            gc_content=total_gc / total if total > 0 else 0,
            n_count=total_n,
            n_percentage=total_n / total * 100 if total > 0 else 0,
            gaps_count=total_gaps,
            gaps_length=total_gap_length,
        )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "total_length": self.total_length,
            "num_contigs": self.num_contigs,
            "largest_contig": self.largest_contig,
            "shortest_contig": self.shortest_contig,
            "mean_length": round(self.mean_length, 1),
            "median_length": round(self.median_length, 1),
            "N50": self.n50,
            "N75": self.n75,
            "N90": self.n90,
            "L50": self.l50,
            "L75": self.l75,
            "L90": self.l90,
            "GC_content": f"{self.gc_content:.2%}",
            "N_count": self.n_count,
            "N_percentage": f"{self.n_percentage:.2f}%",
            "gaps_count": self.gaps_count,
            "gaps_length": self.gaps_length,
        }


@dataclass
class QUASTResult:
    """QUAST-like assembly evaluation result."""

    contigs_stats: ContigStatistics
    contigs_ge_1000: int = 0
    contigs_ge_5000: int = 0
    contigs_ge_10000: int = 0
    contigs_ge_50000: int = 0
    total_length_ge_1000: int = 0
    total_length_ge_5000: int = 0
    total_length_ge_10000: int = 0
    total_length_ge_50000: int = 0

    # Reference-based metrics (if reference provided)
    genome_fraction: float = 0.0
    duplication_ratio: float = 0.0
    largest_alignment: int = 0
    total_aligned_length: int = 0
    num_misassemblies: int = 0
    num_mismatches: int = 0
    num_indels: int = 0
    nga50: int = 0  # NG50 adjusted for aligned length
    nga75: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        result = self.contigs_stats.to_dict()
        result.update(
            {
                "# contigs (>= 1000 bp)": self.contigs_ge_1000,
                "# contigs (>= 5000 bp)": self.contigs_ge_5000,
                "# contigs (>= 10000 bp)": self.contigs_ge_10000,
                "# contigs (>= 50000 bp)": self.contigs_ge_50000,
                "Total length (>= 1000 bp)": self.total_length_ge_1000,
                "Total length (>= 5000 bp)": self.total_length_ge_5000,
                "Total length (>= 10000 bp)": self.total_length_ge_10000,
                "Total length (>= 50000 bp)": self.total_length_ge_50000,
            }
        )

        if self.genome_fraction > 0:
            result.update(
                {
                    "Genome fraction (%)": f"{self.genome_fraction:.2%}",
                    "Duplication ratio": f"{self.duplication_ratio:.3f}",
                    "Largest alignment": self.largest_alignment,
                    "# misassemblies": self.num_misassemblies,
                    "# mismatches per 100 kbp": self.num_mismatches,
                    "# indels per 100 kbp": self.num_indels,
                    "NGA50": self.nga50,
                    "NGA75": self.nga75,
                }
            )

        return result


class AssemblyQC:
    """Assembly quality control and evaluation."""

    def __init__(self, min_contig_length: int = 500):
        self.min_contig_length = min_contig_length

    def evaluate(
        self,
        contigs: list[str],
        reference: str | None = None,
    ) -> QUASTResult:
        """Evaluate assembly quality."""
        # Filter by minimum length
        filtered = [c for c in contigs if len(c) >= self.min_contig_length]

        # Basic statistics
        stats = ContigStatistics.from_sequences(filtered)

        # Length-filtered counts
        lengths = [len(c) for c in filtered]

        result = QUASTResult(
            contigs_stats=stats,
            contigs_ge_1000=sum(1 for l in lengths if l >= 1000),
            contigs_ge_5000=sum(1 for l in lengths if l >= 5000),
            contigs_ge_10000=sum(1 for l in lengths if l >= 10000),
            contigs_ge_50000=sum(1 for l in lengths if l >= 50000),
            total_length_ge_1000=sum(l for l in lengths if l >= 1000),
            total_length_ge_5000=sum(l for l in lengths if l >= 5000),
            total_length_ge_10000=sum(l for l in lengths if l >= 10000),
            total_length_ge_50000=sum(l for l in lengths if l >= 50000),
        )

        # Reference-based evaluation
        if reference:
            ref_metrics = self._evaluate_against_reference(filtered, reference)
            result.genome_fraction = ref_metrics["genome_fraction"]
            result.duplication_ratio = ref_metrics["duplication_ratio"]
            result.largest_alignment = ref_metrics["largest_alignment"]
            result.total_aligned_length = ref_metrics["total_aligned"]
            result.num_misassemblies = ref_metrics["misassemblies"]
            result.num_mismatches = ref_metrics["mismatches"]
            result.num_indels = ref_metrics["indels"]
            result.nga50 = ref_metrics["nga50"]
            result.nga75 = ref_metrics["nga75"]

        return result

    def _evaluate_against_reference(
        self,
        contigs: list[str],
        reference: str,
    ) -> dict:
        """Evaluate assembly against reference genome."""
        logger.info("Evaluating against reference")

        reference = reference.upper()
        ref_length = len(reference)

        # Align contigs to reference
        alignments = self._align_to_reference(contigs, reference)

        # Calculate metrics
        aligned_regions = set()
        total_aligned = 0
        largest_alignment = 0
        mismatches = 0
        indels = 0

        for aln in alignments:
            start, end = aln["ref_start"], aln["ref_end"]
            aligned_regions.update(range(start, end))
            aln_length = end - start
            total_aligned += aln_length
            largest_alignment = max(largest_alignment, aln_length)
            mismatches += aln.get("mismatches", 0)
            indels += aln.get("indels", 0)

        genome_fraction = len(aligned_regions) / ref_length
        duplication_ratio = total_aligned / len(aligned_regions) if aligned_regions else 0

        # Detect misassemblies
        misassemblies = self._detect_misassemblies(alignments)

        # Calculate NGA values
        aligned_lengths = sorted([a["ref_end"] - a["ref_start"] for a in alignments], reverse=True)
        nga50, nga75 = 0, 0
        cumsum = 0

        for length in aligned_lengths:
            cumsum += length
            if cumsum >= ref_length * 0.5 and nga50 == 0:
                nga50 = length
            if cumsum >= ref_length * 0.75 and nga75 == 0:
                nga75 = length

        # Normalize mismatches/indels per 100 kbp
        if total_aligned > 0:
            mismatches = int(mismatches / total_aligned * 100000)
            indels = int(indels / total_aligned * 100000)

        return {
            "genome_fraction": genome_fraction,
            "duplication_ratio": duplication_ratio,
            "largest_alignment": largest_alignment,
            "total_aligned": total_aligned,
            "misassemblies": misassemblies,
            "mismatches": mismatches,
            "indels": indels,
            "nga50": nga50,
            "nga75": nga75,
        }

    def _align_to_reference(
        self,
        contigs: list[str],
        reference: str,
    ) -> list[dict]:
        """Align contigs to reference using k-mer seeding."""
        k = 21
        alignments = []

        # Build reference k-mer index
        ref_index: dict[str, list[int]] = defaultdict(list)
        for i in range(len(reference) - k + 1):
            kmer = reference[i : i + k]
            if "N" not in kmer:
                ref_index[kmer].append(i)

        for contig_idx, contig in enumerate(contigs):
            contig = contig.upper()

            # Find seed matches
            matches = defaultdict(int)
            for i in range(len(contig) - k + 1):
                kmer = contig[i : i + k]
                for ref_pos in ref_index.get(kmer, []):
                    # Estimate alignment start
                    aln_start = ref_pos - i
                    if 0 <= aln_start <= len(reference) - len(contig):
                        matches[aln_start] += 1

            if matches:
                # Find best alignment
                best_start = max(matches.keys(), key=lambda s: matches[s])
                seed_count = matches[best_start]

                # Extend alignment
                ref_region = reference[best_start : best_start + len(contig)]

                # Count mismatches and indels (simple comparison)
                mm = 0
                for a, b in zip(contig, ref_region, strict=False):
                    if a != b:
                        mm += 1

                identity = 1 - mm / len(contig) if len(contig) > 0 else 0

                if identity > 0.8 and seed_count >= 5:
                    alignments.append(
                        {
                            "contig_idx": contig_idx,
                            "ref_start": best_start,
                            "ref_end": best_start + len(contig),
                            "identity": identity,
                            "mismatches": mm,
                            "indels": 0,  # Simplified
                        }
                    )

        return alignments

    def _detect_misassemblies(self, alignments: list[dict]) -> int:
        """Detect potential misassemblies from alignments."""
        misassemblies = 0

        # Sort alignments by contig
        by_contig = defaultdict(list)
        for aln in alignments:
            by_contig[aln["contig_idx"]].append(aln)

        for _contig_idx, alns in by_contig.items():
            if len(alns) > 1:
                # Multiple alignments for same contig - potential misassembly
                alns.sort(key=lambda a: a["ref_start"])

                for i in range(len(alns) - 1):
                    # Check for relocations/inversions
                    gap = alns[i + 1]["ref_start"] - alns[i]["ref_end"]
                    if gap > 1000 or gap < -1000:  # Large gap or overlap
                        misassemblies += 1

        return misassemblies


@dataclass
class BUSCOResult:
    """BUSCO analysis result."""

    complete: int = 0
    complete_single: int = 0
    complete_duplicated: int = 0
    fragmented: int = 0
    missing: int = 0
    total: int = 0

    @property
    def complete_percentage(self) -> float:
        return self.complete / self.total * 100 if self.total > 0 else 0

    @property
    def summary(self) -> str:
        return (
            f"C:{self.complete_percentage:.1f}%"
            f"[S:{self.complete_single / self.total * 100:.1f}%,"
            f"D:{self.complete_duplicated / self.total * 100:.1f}%],"
            f"F:{self.fragmented / self.total * 100:.1f}%,"
            f"M:{self.missing / self.total * 100:.1f}%,"
            f"n:{self.total}"
        )

    def to_dict(self) -> dict:
        return {
            "Complete BUSCOs": self.complete,
            "Complete single-copy": self.complete_single,
            "Complete duplicated": self.complete_duplicated,
            "Fragmented BUSCOs": self.fragmented,
            "Missing BUSCOs": self.missing,
            "Total BUSCO groups": self.total,
            "Complete (%)": f"{self.complete_percentage:.1f}%",
        }


class BUSCOAnalysis:
    """BUSCO-like analysis for assembly completeness."""

    def __init__(
        self,
        lineage_markers: dict[str, str] | None = None,
    ):
        self.lineage_markers = lineage_markers or self._load_default_markers()

    def _load_default_markers(self) -> dict[str, str]:
        """Short universal marker k-mers for BUSCO-style completeness heuristics.

        Replace with lineage-specific ``odb`` marker tables from the BUSCO distribution
        when running real assemblies.
        """
        return {
            "18S_euk_5prime": "GTAGTCATATGCTTGTCTC",
            "28S_euk_core": "ACCTGTTGATCCGCCA",
            "16S_bact_conserved": "AGAGTTTGATCCTGGCTCAG",
            "rpoB_seed": "ATGGCAATCGCTGAA",
            "gyrB_seed": "ATGAGCGATCTGGCG",
        }

    def analyze(
        self,
        contigs: list[str],
        mode: str = "genome",  # genome, transcriptome, proteins
    ) -> BUSCOResult:
        """Run BUSCO analysis."""
        logger.info(f"Running BUSCO analysis in {mode} mode")

        total = len(self.lineage_markers)
        complete_single = 0
        complete_duplicated = 0
        fragmented = 0

        # Concatenate all contigs for searching
        assembly = "".join(c.upper() for c in contigs)

        for _marker_id, marker_seq in self.lineage_markers.items():
            # Search for marker
            status = self._search_marker(assembly, marker_seq)

            if status == "complete_single":
                complete_single += 1
            elif status == "complete_duplicated":
                complete_duplicated += 1
            elif status == "fragmented":
                fragmented += 1

        complete = complete_single + complete_duplicated
        missing = total - complete - fragmented

        return BUSCOResult(
            complete=complete,
            complete_single=complete_single,
            complete_duplicated=complete_duplicated,
            fragmented=fragmented,
            missing=missing,
            total=total,
        )

    def _search_marker(
        self,
        assembly: str,
        marker_seq: str,
    ) -> str:
        """Search for marker in assembly."""
        marker_seq = marker_seq.upper()

        # Count occurrences
        count = assembly.count(marker_seq)

        if count == 0:
            # Try partial match
            partial_len = len(marker_seq) // 2
            if marker_seq[:partial_len] in assembly or marker_seq[-partial_len:] in assembly:
                return "fragmented"
            return "missing"
        elif count == 1:
            return "complete_single"
        else:
            return "complete_duplicated"


class KmerCompleteness:
    """Assess assembly completeness using k-mer analysis."""

    def __init__(self, k: int = 21):
        self.k = k

    def analyze(
        self,
        assembly: list[str],
        reads: list[str],
    ) -> dict:
        """Analyze k-mer completeness."""
        logger.info("Analyzing k-mer completeness")

        # Count k-mers in reads
        read_kmers = self._count_kmers(reads)

        # Count k-mers in assembly
        assembly_text = "".join(assembly)
        assembly_kmers = set()

        for i in range(len(assembly_text) - self.k + 1):
            kmer = assembly_text[i : i + self.k]
            if "N" not in kmer:
                canonical = min(kmer, self._reverse_complement(kmer))
                assembly_kmers.add(canonical)

        # Calculate metrics
        solid_kmers = {k for k, c in read_kmers.items() if c >= 3}

        found = assembly_kmers & solid_kmers
        missing = solid_kmers - assembly_kmers
        extra = assembly_kmers - solid_kmers

        completeness = len(found) / len(solid_kmers) if solid_kmers else 0

        return {
            "total_read_kmers": len(read_kmers),
            "solid_read_kmers": len(solid_kmers),
            "assembly_kmers": len(assembly_kmers),
            "found_kmers": len(found),
            "missing_kmers": len(missing),
            "extra_kmers": len(extra),
            "completeness": f"{completeness:.2%}",
            "qv_estimate": -10 * np.log10(1 - completeness) if completeness < 1 else 50,
        }

    def _count_kmers(self, sequences: list[str]) -> dict[str, int]:
        """Count k-mers in sequences."""
        counts = defaultdict(int)

        for seq in sequences:
            seq = seq.upper()
            for i in range(len(seq) - self.k + 1):
                kmer = seq[i : i + self.k]
                if "N" not in kmer:
                    canonical = min(kmer, self._reverse_complement(kmer))
                    counts[canonical] += 1

        return dict(counts)

    def _reverse_complement(self, seq: str) -> str:
        """Get reverse complement."""
        complement = {"A": "T", "T": "A", "G": "C", "C": "G"}
        return "".join(complement.get(b, "N") for b in reversed(seq))


class AssemblyComparison:
    """Compare multiple assemblies."""

    def compare(
        self,
        assemblies: dict[str, list[str]],
        reference: str | None = None,
    ) -> dict:
        """Compare multiple assemblies."""
        qc = AssemblyQC()
        results = {}

        for name, contigs in assemblies.items():
            result = qc.evaluate(contigs, reference)
            results[name] = result.to_dict()

        return results

    def rank_assemblies(
        self,
        assemblies: dict[str, list[str]],
        weights: dict[str, float] | None = None,
    ) -> list[tuple[str, float]]:
        """Rank assemblies by weighted score."""
        weights = weights or {
            "n50": 0.3,
            "total_length": 0.2,
            "num_contigs": -0.1,  # Fewer is better
            "gc_content": 0.0,  # Neutral
            "n_percentage": -0.1,  # Lower is better
        }

        scores = []

        for name, contigs in assemblies.items():
            stats = ContigStatistics.from_sequences(contigs)

            score = 0
            score += weights.get("n50", 0) * stats.n50 / 1000000  # Normalize
            score += weights.get("total_length", 0) * stats.total_length / 1000000000
            score += weights.get("num_contigs", 0) * stats.num_contigs / 1000
            score += weights.get("n_percentage", 0) * stats.n_percentage

            scores.append((name, score))

        return sorted(scores, key=lambda x: -x[1])

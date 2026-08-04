"""Scaffolding Module.
==================

Tools for ordering, orienting, and connecting contigs into scaffolds.
"""

import logging
from collections import defaultdict
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ScaffoldComponent:
    """Component of a scaffold (contig with orientation and gap)."""

    contig_id: str
    sequence: str
    orientation: str  # '+' or '-'
    gap_before: int = 0  # Gap size before this component


@dataclass
class Scaffold:
    """Scaffold composed of ordered, oriented contigs."""

    id: str
    components: list[ScaffoldComponent]

    @property
    def sequence(self) -> str:
        """Get scaffold sequence with gaps as N's."""
        parts = []
        for comp in self.components:
            if comp.gap_before > 0:
                parts.append("N" * comp.gap_before)

            if comp.orientation == "+":
                parts.append(comp.sequence)
            else:
                # Reverse complement
                complement = {"A": "T", "T": "A", "G": "C", "C": "G", "N": "N"}
                revcomp = "".join(complement.get(b, "N") for b in reversed(comp.sequence))
                parts.append(revcomp)

        return "".join(parts)

    @property
    def length(self) -> int:
        return len(self.sequence)

    @property
    def num_components(self) -> int:
        return len(self.components)

    @property
    def total_gap_length(self) -> int:
        return sum(c.gap_before for c in self.components)

    def to_agp(self) -> str:
        """Convert to AGP format."""
        lines = []
        pos = 1
        part = 1

        for comp in self.components:
            if comp.gap_before > 0:
                # Gap line
                end = pos + comp.gap_before - 1
                lines.append(
                    f"{self.id}\t{pos}\t{end}\t{part}\tN\t{comp.gap_before}\tscaffold\tyes\tpaired-ends"
                )
                pos = end + 1
                part += 1

            # Contig line
            comp_len = len(comp.sequence)
            end = pos + comp_len - 1
            lines.append(
                f"{self.id}\t{pos}\t{end}\t{part}\tW\t{comp.contig_id}\t1\t{comp_len}\t{comp.orientation}"
            )
            pos = end + 1
            part += 1

        return "\n".join(lines)


@dataclass
class ScaffoldLink:
    """Link between two contigs."""

    contig1_id: str
    contig1_end: str  # '5' or '3'
    contig2_id: str
    contig2_end: str
    gap_size: int
    support: int  # Number of supporting pairs/reads
    link_type: str  # 'paired_end', 'mate_pair', 'long_read', 'optical'


class ScaffoldGraph:
    """Graph of scaffold links between contigs."""

    def __init__(self):
        self.links: list[ScaffoldLink] = []
        self.adjacency: dict[str, list[ScaffoldLink]] = defaultdict(list)

    def add_link(self, link: ScaffoldLink):
        """Add a scaffold link."""
        self.links.append(link)
        self.adjacency[link.contig1_id].append(link)
        self.adjacency[link.contig2_id].append(link)

    def get_links_for_contig(self, contig_id: str) -> list[ScaffoldLink]:
        """Get all links involving a contig."""
        return self.adjacency.get(contig_id, [])

    def get_best_link(
        self,
        contig_id: str,
        end: str,
        min_support: int = 2,
    ) -> ScaffoldLink | None:
        """Get best link from contig end."""
        candidates = []
        for link in self.adjacency.get(contig_id, []):
            if (
                link.contig1_id == contig_id
                and link.contig1_end == end
                or link.contig2_id == contig_id
                and link.contig2_end == end
            ):
                if link.support >= min_support:
                    candidates.append(link)

        if candidates:
            return max(candidates, key=lambda l: l.support)
        return None


class Scaffolder:
    """Scaffold contigs using various linking evidence."""

    def __init__(
        self,
        min_link_support: int = 2,
        min_contig_length: int = 500,
    ):
        self.min_link_support = min_link_support
        self.min_contig_length = min_contig_length
        self.graph = ScaffoldGraph()

    def scaffold_with_paired_reads(
        self,
        contigs: list["Contig"],
        read_pairs: list[tuple[str, str]],
        insert_size_mean: int = 500,
        insert_size_std: int = 100,
    ) -> list[Scaffold]:
        """Scaffold using paired-end reads."""
        logger.info("Scaffolding with paired-end reads")

        # Map reads to contigs
        contig_map = self._map_reads_to_contigs(contigs, read_pairs)

        # Find links from mapped pairs
        self._find_links_from_pairs(
            contig_map,
            contigs,
            insert_size_mean,
            insert_size_std,
        )

        # Build scaffolds
        scaffolds = self._build_scaffolds(contigs)

        return scaffolds

    def scaffold_with_long_reads(
        self,
        contigs: list["Contig"],
        long_reads: list[str],
    ) -> list[Scaffold]:
        """Scaffold using long reads."""
        logger.info("Scaffolding with long reads")

        # Map long reads to multiple contigs
        contig_alignments = self._map_long_reads_to_contigs(contigs, long_reads)

        # Find links
        self._find_links_from_long_reads(contig_alignments, contigs)

        # Build scaffolds
        scaffolds = self._build_scaffolds(contigs)

        return scaffolds

    def scaffold_with_hic(
        self,
        contigs: list["Contig"],
        hic_contacts: list[tuple[str, int, str, int]],
    ) -> list[Scaffold]:
        """Scaffold using Hi-C contact data."""
        logger.info("Scaffolding with Hi-C data")

        # Build contact matrix
        contact_matrix = self._build_hic_contact_matrix(contigs, hic_contacts)

        # Cluster and order contigs
        ordering = self._order_contigs_by_hic(contigs, contact_matrix)

        # Build scaffolds
        scaffolds = self._build_scaffolds_from_ordering(contigs, ordering)

        return scaffolds

    def _map_reads_to_contigs(
        self,
        contigs: list["Contig"],
        read_pairs: list[tuple[str, str]],
    ) -> dict[str, list[tuple[str, int, str]]]:
        """Map read pairs to contigs."""
        k = 21

        # Build k-mer index for contigs
        kmer_index: dict[str, list[tuple[str, int]]] = defaultdict(list)

        for contig in contigs:
            for i in range(len(contig.sequence) - k + 1):
                kmer = contig.sequence[i : i + k]
                if "N" not in kmer:
                    kmer_index[kmer].append((contig.id, i))

        # Map reads
        mapped = defaultdict(list)

        for pair_idx, (read1, read2) in enumerate(read_pairs):
            read1 = read1.upper()
            read2 = read2.upper()

            # Find best mapping for read1
            r1_matches = defaultdict(int)
            for i in range(len(read1) - k + 1):
                kmer = read1[i : i + k]
                for contig_id, pos in kmer_index.get(kmer, []):
                    r1_matches[(contig_id, pos - i)] += 1

            # Find best mapping for read2
            r2_matches = defaultdict(int)
            for i in range(len(read2) - k + 1):
                kmer = read2[i : i + k]
                for contig_id, pos in kmer_index.get(kmer, []):
                    r2_matches[(contig_id, pos - i)] += 1

            if r1_matches and r2_matches:
                best_r1 = max(r1_matches.keys(), key=lambda k: r1_matches[k])
                best_r2 = max(r2_matches.keys(), key=lambda k: r2_matches[k])

                mapped[pair_idx].append((best_r1[0], best_r1[1], "R1"))
                mapped[pair_idx].append((best_r2[0], best_r2[1], "R2"))

        return dict(mapped)

    def _find_links_from_pairs(
        self,
        contig_map: dict[str, list[tuple[str, int, str]]],
        contigs: list["Contig"],
        insert_size_mean: int,
        insert_size_std: int,
    ):
        """Find scaffold links from paired-end mappings."""
        contig_lengths = {c.id: c.length for c in contigs}
        link_counts: dict[tuple, list[int]] = defaultdict(list)

        for _pair_idx, mappings in contig_map.items():
            if len(mappings) != 2:
                continue

            contig1, pos1, _ = mappings[0]
            contig2, pos2, _ = mappings[1]

            # Skip if same contig
            if contig1 == contig2:
                continue

            # Determine ends
            c1_len = contig_lengths.get(contig1, 0)
            c2_len = contig_lengths.get(contig2, 0)

            c1_end = "3" if pos1 > c1_len / 2 else "5"
            c2_end = "3" if pos2 > c2_len / 2 else "5"

            # Estimate gap size
            dist_to_end1 = c1_len - pos1 if c1_end == "3" else pos1

            dist_to_end2 = pos2 if c2_end == "5" else c2_len - pos2

            gap_size = insert_size_mean - dist_to_end1 - dist_to_end2

            # Record link
            key = (contig1, c1_end, contig2, c2_end)
            link_counts[key].append(gap_size)

        # Create links
        for (c1, e1, c2, e2), gaps in link_counts.items():
            if len(gaps) >= self.min_link_support:
                self.graph.add_link(
                    ScaffoldLink(
                        contig1_id=c1,
                        contig1_end=e1,
                        contig2_id=c2,
                        contig2_end=e2,
                        gap_size=int(np.median(gaps)),
                        support=len(gaps),
                        link_type="paired_end",
                    )
                )

    def _map_long_reads_to_contigs(
        self,
        contigs: list["Contig"],
        long_reads: list[str],
    ) -> list[list[tuple[str, int, int, str]]]:
        """Map long reads to multiple contigs."""
        k = 15

        # Build k-mer index
        kmer_index: dict[str, list[tuple[str, int]]] = defaultdict(list)
        for contig in contigs:
            for i in range(len(contig.sequence) - k + 1):
                kmer = contig.sequence[i : i + k]
                if "N" not in kmer:
                    kmer_index[kmer].append((contig.id, i))

        alignments = []

        for read in long_reads:
            read = read.upper()
            read_alignments = []

            # Find matching k-mers
            matches: dict[str, list[tuple[int, int]]] = defaultdict(list)

            for i in range(len(read) - k + 1):
                kmer = read[i : i + k]
                for contig_id, contig_pos in kmer_index.get(kmer, []):
                    matches[contig_id].append((i, contig_pos))

            # Find best alignment to each contig
            for contig_id, positions in matches.items():
                if len(positions) >= 3:  # Minimum k-mer matches
                    positions.sort()

                    # Find consistent chain
                    read_start = positions[0][0]
                    read_end = positions[-1][0] + k

                    strand = "+"
                    read_alignments.append(
                        (
                            contig_id,
                            read_start,
                            read_end,
                            strand,
                        )
                    )

            if len(read_alignments) >= 2:
                alignments.append(read_alignments)

        return alignments

    def _find_links_from_long_reads(
        self,
        alignments: list[list[tuple[str, int, int, str]]],
        contigs: list["Contig"],
    ):
        """Find scaffold links from long read alignments."""
        {c.id: c.length for c in contigs}
        link_counts: dict[tuple, list[int]] = defaultdict(list)

        for read_alignments in alignments:
            # Sort by read position
            sorted_alns = sorted(read_alignments, key=lambda x: x[1])

            for i in range(len(sorted_alns) - 1):
                c1, r1_start, r1_end, s1 = sorted_alns[i]
                c2, r2_start, r2_end, s2 = sorted_alns[i + 1]

                if c1 == c2:
                    continue

                # Determine ends based on alignment position
                c1_end = "3"  # Simplified
                c2_end = "5"

                gap_size = r2_start - r1_end

                key = (c1, c1_end, c2, c2_end)
                link_counts[key].append(gap_size)

        for (c1, e1, c2, e2), gaps in link_counts.items():
            if len(gaps) >= self.min_link_support:
                self.graph.add_link(
                    ScaffoldLink(
                        contig1_id=c1,
                        contig1_end=e1,
                        contig2_id=c2,
                        contig2_end=e2,
                        gap_size=int(np.median(gaps)),
                        support=len(gaps),
                        link_type="long_read",
                    )
                )

    def _build_hic_contact_matrix(
        self,
        contigs: list["Contig"],
        hic_contacts: list[tuple[str, int, str, int]],
    ) -> np.ndarray:
        """Build Hi-C contact matrix between contigs."""
        n = len(contigs)
        contig_idx = {c.id: i for i, c in enumerate(contigs)}

        matrix = np.zeros((n, n))

        for chrom1, _pos1, chrom2, _pos2 in hic_contacts:
            if chrom1 in contig_idx and chrom2 in contig_idx:
                i = contig_idx[chrom1]
                j = contig_idx[chrom2]
                matrix[i, j] += 1
                matrix[j, i] += 1

        return matrix

    def _order_contigs_by_hic(
        self,
        contigs: list["Contig"],
        contact_matrix: np.ndarray,
    ) -> list[tuple[str, str]]:
        """Order contigs using Hi-C contact matrix."""
        n = len(contigs)

        # Simple greedy ordering
        used = set()
        ordering = []

        # Start with contig with most contacts
        start_idx = np.argmax(contact_matrix.sum(axis=1))
        ordering.append((contigs[start_idx].id, "+"))
        used.add(start_idx)

        while len(used) < n:
            current_idx = [i for i, c in enumerate(contigs) if c.id == ordering[-1][0]][0]

            # Find best next contig
            best_idx = None
            best_score = 0

            for j in range(n):
                if j not in used:
                    score = contact_matrix[current_idx, j]
                    if score > best_score:
                        best_score = score
                        best_idx = j

            if best_idx is not None:
                ordering.append((contigs[best_idx].id, "+"))
                used.add(best_idx)
            else:
                # Add remaining contigs
                for j in range(n):
                    if j not in used:
                        ordering.append((contigs[j].id, "+"))
                        used.add(j)

        return ordering

    def _build_scaffolds_from_ordering(
        self,
        contigs: list["Contig"],
        ordering: list[tuple[str, str]],
    ) -> list[Scaffold]:
        """Build scaffolds from ordered contigs."""
        contig_dict = {c.id: c for c in contigs}

        components = []
        for contig_id, orientation in ordering:
            contig = contig_dict.get(contig_id)
            if contig:
                components.append(
                    ScaffoldComponent(
                        contig_id=contig_id,
                        sequence=contig.sequence,
                        orientation=orientation,
                        gap_before=100 if components else 0,  # Default gap
                    )
                )

        return [Scaffold(id="scaffold_0", components=components)]

    def _build_scaffolds(self, contigs: list["Contig"]) -> list[Scaffold]:
        """Build scaffolds from link graph."""
        contig_dict = {c.id: c for c in contigs}
        used = set()
        scaffolds = []
        scaffold_id = 0

        for contig in sorted(contigs, key=lambda c: c.length, reverse=True):
            if contig.id in used:
                continue

            if contig.length < self.min_contig_length:
                continue

            # Start new scaffold
            components = [
                ScaffoldComponent(
                    contig_id=contig.id,
                    sequence=contig.sequence,
                    orientation="+",
                    gap_before=0,
                )
            ]
            used.add(contig.id)

            # Extend 3' end
            current = contig.id
            current_end = "3"

            while True:
                link = self.graph.get_best_link(current, current_end, self.min_link_support)

                if link is None:
                    break

                # Find next contig
                if link.contig1_id == current:
                    next_id = link.contig2_id
                    next_entry_end = link.contig2_end
                else:
                    next_id = link.contig1_id
                    next_entry_end = link.contig1_end

                if next_id in used:
                    break

                next_contig = contig_dict.get(next_id)
                if not next_contig:
                    break

                # Determine orientation
                orientation = "+" if next_entry_end == "5" else "-"

                components.append(
                    ScaffoldComponent(
                        contig_id=next_id,
                        sequence=next_contig.sequence,
                        orientation=orientation,
                        gap_before=max(1, link.gap_size),
                    )
                )
                used.add(next_id)

                current = next_id
                current_end = "3" if orientation == "+" else "5"

            scaffolds.append(
                Scaffold(
                    id=f"scaffold_{scaffold_id}",
                    components=components,
                )
            )
            scaffold_id += 1

        # Add unused contigs as single-contig scaffolds
        for contig in contigs:
            if contig.id not in used:
                scaffolds.append(
                    Scaffold(
                        id=f"scaffold_{scaffold_id}",
                        components=[
                            ScaffoldComponent(
                                contig_id=contig.id,
                                sequence=contig.sequence,
                                orientation="+",
                                gap_before=0,
                            )
                        ],
                    )
                )
                scaffold_id += 1

        return scaffolds


class GapFiller:
    """Fill gaps in scaffolds using various data sources."""

    def __init__(self, min_overlap: int = 20):
        self.min_overlap = min_overlap

    def fill_with_reads(
        self,
        scaffold: Scaffold,
        reads: list[str],
    ) -> Scaffold:
        """Fill gaps using read sequences."""
        new_components = []

        for i, comp in enumerate(scaffold.components):
            if i == 0:
                new_components.append(comp)
                continue

            prev_comp = scaffold.components[i - 1]

            if comp.gap_before > 0:
                # Try to fill gap
                left_flank = self._get_right_flank(prev_comp)
                right_flank = self._get_left_flank(comp)

                gap_seq = self._find_gap_filling_sequence(
                    left_flank,
                    right_flank,
                    reads,
                    comp.gap_before,
                )

                if gap_seq:
                    # Add gap sequence as component
                    new_components.append(
                        ScaffoldComponent(
                            contig_id=f"gap_fill_{i}",
                            sequence=gap_seq,
                            orientation="+",
                            gap_before=0,
                        )
                    )

                    # Add current component without gap
                    new_components.append(
                        ScaffoldComponent(
                            contig_id=comp.contig_id,
                            sequence=comp.sequence,
                            orientation=comp.orientation,
                            gap_before=0,
                        )
                    )
                else:
                    new_components.append(comp)
            else:
                new_components.append(comp)

        return Scaffold(id=scaffold.id, components=new_components)

    def _get_right_flank(self, comp: ScaffoldComponent, length: int = 100) -> str:
        """Get right flank of component."""
        if comp.orientation == "+":
            return comp.sequence[-length:]
        else:
            seq = comp.sequence[:length]
            complement = {"A": "T", "T": "A", "G": "C", "C": "G", "N": "N"}
            return "".join(complement.get(b, "N") for b in reversed(seq))

    def _get_left_flank(self, comp: ScaffoldComponent, length: int = 100) -> str:
        """Get left flank of component."""
        if comp.orientation == "+":
            return comp.sequence[:length]
        else:
            seq = comp.sequence[-length:]
            complement = {"A": "T", "T": "A", "G": "C", "C": "G", "N": "N"}
            return "".join(complement.get(b, "N") for b in reversed(seq))

    def _find_gap_filling_sequence(
        self,
        left_flank: str,
        right_flank: str,
        reads: list[str],
        expected_gap: int,
    ) -> str | None:
        """Find sequence to fill gap."""
        left_kmer = left_flank[-self.min_overlap :]
        right_kmer = right_flank[: self.min_overlap]

        for read in reads:
            read = read.upper()

            left_pos = read.find(left_kmer)
            right_pos = read.find(right_kmer)

            if left_pos != -1 and right_pos != -1 and left_pos < right_pos:
                gap_seq = read[left_pos + len(left_kmer) : right_pos]

                # Check if reasonable length
                if abs(len(gap_seq) - expected_gap) < expected_gap * 0.5:
                    return gap_seq

        return None

    def fill_with_local_assembly(
        self,
        scaffold: Scaffold,
        reads: list[str],
        k: int = 31,
    ) -> Scaffold:
        """Fill gaps using local de Bruijn assembly."""
        from .assemblers import DeBruijnAssembler

        new_components = []

        for i, comp in enumerate(scaffold.components):
            if i == 0:
                new_components.append(comp)
                continue

            prev_comp = scaffold.components[i - 1]

            if comp.gap_before > 50:  # Only try for gaps > 50bp
                left_flank = self._get_right_flank(prev_comp, 200)
                right_flank = self._get_left_flank(comp, 200)

                # Find reads spanning or near gap
                gap_reads = self._find_gap_reads(left_flank, right_flank, reads)

                if len(gap_reads) >= 5:
                    # Local assembly
                    assembler = DeBruijnAssembler(k=k)
                    result = assembler.assemble(gap_reads)

                    if result.contigs:
                        # Find contig that bridges gap
                        bridge = self._find_bridge_contig(
                            result.contigs,
                            left_flank,
                            right_flank,
                        )

                        if bridge:
                            new_components.append(
                                ScaffoldComponent(
                                    contig_id=f"local_assembly_{i}",
                                    sequence=bridge,
                                    orientation="+",
                                    gap_before=0,
                                )
                            )

                            new_components.append(
                                ScaffoldComponent(
                                    contig_id=comp.contig_id,
                                    sequence=comp.sequence,
                                    orientation=comp.orientation,
                                    gap_before=0,
                                )
                            )
                            continue

            new_components.append(comp)

        return Scaffold(id=scaffold.id, components=new_components)

    def _find_gap_reads(
        self,
        left_flank: str,
        right_flank: str,
        reads: list[str],
    ) -> list[str]:
        """Find reads that may span the gap."""
        k = 15
        left_kmers = {left_flank[i : i + k] for i in range(len(left_flank) - k + 1)}
        right_kmers = {right_flank[i : i + k] for i in range(len(right_flank) - k + 1)}

        gap_reads = []
        for read in reads:
            read_upper = read.upper()
            read_kmers = {read_upper[i : i + k] for i in range(len(read_upper) - k + 1)}

            # Check if read overlaps with flanks
            if read_kmers & left_kmers or read_kmers & right_kmers:
                gap_reads.append(read)

        return gap_reads

    def _find_bridge_contig(
        self,
        contigs: list,
        left_flank: str,
        right_flank: str,
    ) -> str | None:
        """Find contig that bridges left and right flanks."""
        k = 15

        for contig in contigs:
            seq = contig.sequence.upper()

            # Check if contig overlaps both flanks
            left_match = any(left_flank[i : i + k] in seq for i in range(len(left_flank) - k + 1))
            right_match = any(
                right_flank[i : i + k] in seq for i in range(len(right_flank) - k + 1)
            )

            if left_match and right_match:
                return seq

        return None

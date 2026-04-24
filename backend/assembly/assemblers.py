"""
Genome Assemblers
=================

De novo and reference-guided genome assembly implementations.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Set, Iterator
from collections import defaultdict
import numpy as np
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


@dataclass
class Contig:
    """Assembled contig."""
    id: str
    sequence: str
    coverage: float = 0.0
    length: int = 0
    gc_content: float = 0.0
    quality_scores: Optional[List[int]] = None
    source_reads: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        if self.length == 0:
            self.length = len(self.sequence)
        if self.gc_content == 0:
            gc = self.sequence.upper().count('G') + self.sequence.upper().count('C')
            self.gc_content = gc / self.length if self.length > 0 else 0


@dataclass
class AssemblyResult:
    """Result of genome assembly."""
    contigs: List[Contig]
    scaffolds: Optional[List["Scaffold"]] = None
    total_length: int = 0
    n50: int = 0
    n90: int = 0
    l50: int = 0
    l90: int = 0
    largest_contig: int = 0
    gc_content: float = 0.0
    num_contigs: int = 0
    num_scaffolds: int = 0
    gaps_count: int = 0
    gaps_length: int = 0
    coverage_mean: float = 0.0
    coverage_std: float = 0.0
    assembly_graph: Optional["AssemblyGraph"] = None
    parameters: Dict = field(default_factory=dict)
    
    def __post_init__(self):
        if self.contigs:
            self._calculate_statistics()
    
    def _calculate_statistics(self):
        """Calculate assembly statistics."""
        lengths = sorted([c.length for c in self.contigs], reverse=True)
        
        self.num_contigs = len(self.contigs)
        self.total_length = sum(lengths)
        self.largest_contig = lengths[0] if lengths else 0
        
        # Calculate N50, N90, L50, L90
        cumsum = 0
        for i, length in enumerate(lengths):
            cumsum += length
            if cumsum >= self.total_length * 0.5 and self.n50 == 0:
                self.n50 = length
                self.l50 = i + 1
            if cumsum >= self.total_length * 0.9 and self.n90 == 0:
                self.n90 = length
                self.l90 = i + 1
        
        # GC content
        total_gc = sum(c.gc_content * c.length for c in self.contigs)
        self.gc_content = total_gc / self.total_length if self.total_length > 0 else 0
        
        # Coverage
        coverages = [c.coverage for c in self.contigs if c.coverage > 0]
        if coverages:
            self.coverage_mean = np.mean(coverages)
            self.coverage_std = np.std(coverages)
    
    def get_summary(self) -> Dict:
        """Get assembly summary."""
        return {
            'num_contigs': self.num_contigs,
            'total_length': self.total_length,
            'largest_contig': self.largest_contig,
            'n50': self.n50,
            'n90': self.n90,
            'l50': self.l50,
            'l90': self.l90,
            'gc_content': f"{self.gc_content:.2%}",
            'coverage_mean': f"{self.coverage_mean:.1f}x",
        }
    
    def to_fasta(self, filepath: Optional[Path] = None) -> str:
        """Export contigs to FASTA format."""
        fasta_lines = []
        for contig in self.contigs:
            fasta_lines.append(f">{contig.id} length={contig.length} coverage={contig.coverage:.1f}")
            # Write sequence in 60-character lines
            seq = contig.sequence
            for i in range(0, len(seq), 60):
                fasta_lines.append(seq[i:i+60])
        
        fasta_content = '\n'.join(fasta_lines)
        
        if filepath:
            with open(filepath, 'w') as f:
                f.write(fasta_content)
        
        return fasta_content


class Assembler(ABC):
    """Abstract base class for genome assemblers."""
    
    def __init__(self, params: Optional[Dict] = None):
        self.params = params or {}
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @abstractmethod
    def assemble(self, reads: List[str]) -> AssemblyResult:
        """Assemble reads into contigs."""
        pass
    
    @abstractmethod
    def get_assembly_graph(self) -> "AssemblyGraph":
        """Get the assembly graph."""
        pass


class DeBruijnAssembler(Assembler):
    """De Bruijn graph-based assembler for short reads."""
    
    def __init__(self, k: int = 31, params: Optional[Dict] = None):
        super().__init__(params)
        self.k = k
        self.graph: Dict[str, Set[str]] = defaultdict(set)
        self.kmer_coverage: Dict[str, int] = defaultdict(int)
        self.in_degree: Dict[str, int] = defaultdict(int)
        self.out_degree: Dict[str, int] = defaultdict(int)
    
    def assemble(self, reads: List[str]) -> AssemblyResult:
        """Assemble reads using de Bruijn graph approach."""
        self.logger.info(f"Building de Bruijn graph with k={self.k}")
        
        # Build graph from reads
        self._build_graph(reads)
        
        # Simplify graph
        self._remove_tips()
        self._remove_bubbles()
        
        # Extract contigs
        contigs = self._extract_contigs()
        
        return AssemblyResult(
            contigs=contigs,
            parameters={'k': self.k, 'algorithm': 'de_bruijn'},
        )
    
    def _build_graph(self, reads: List[str]):
        """Build de Bruijn graph from reads."""
        for read in reads:
            read = read.upper()
            
            # Extract k-mers
            for i in range(len(read) - self.k + 1):
                kmer = read[i:i + self.k]
                
                if 'N' in kmer:
                    continue
                
                # Use canonical k-mer
                revcomp = self._reverse_complement(kmer)
                canonical = min(kmer, revcomp)
                self.kmer_coverage[canonical] += 1
                
                if i < len(read) - self.k:
                    next_kmer = read[i + 1:i + 1 + self.k]
                    if 'N' not in next_kmer:
                        # Add edge
                        prefix = kmer[:-1]
                        suffix = kmer[1:]
                        self.graph[prefix].add(suffix)
                        self.out_degree[prefix] += 1
                        self.in_degree[suffix] += 1
    
    def _reverse_complement(self, seq: str) -> str:
        """Get reverse complement."""
        complement = {'A': 'T', 'T': 'A', 'G': 'C', 'C': 'G', 'N': 'N'}
        return ''.join(complement.get(b, 'N') for b in reversed(seq))
    
    def _remove_tips(self, max_length: int = None):
        """Remove short dead-end tips from graph."""
        if max_length is None:
            max_length = 2 * self.k
        
        tips_removed = 0
        
        # Find nodes with in_degree=1, out_degree=0 or in_degree=0, out_degree=1
        for node in list(self.graph.keys()):
            if self.out_degree[node] == 0 and self.in_degree[node] == 1:
                # Trace back and remove if short
                path = [node]
                current = node
                
                while len(path) < max_length:
                    predecessors = [n for n, edges in self.graph.items() if current in edges]
                    if len(predecessors) != 1:
                        break
                    pred = predecessors[0]
                    if self.out_degree[pred] != 1:
                        break
                    path.append(pred)
                    current = pred
                
                if len(path) < max_length:
                    # Remove tip
                    for n in path:
                        if n in self.graph:
                            del self.graph[n]
                    tips_removed += 1
        
        self.logger.info(f"Removed {tips_removed} tips")
    
    def _remove_bubbles(self):
        """Remove simple bubbles from graph."""
        bubbles_removed = 0
        
        # Find nodes with out_degree > 1
        for node in list(self.graph.keys()):
            if len(self.graph.get(node, set())) > 1:
                successors = list(self.graph[node])
                
                # Check if successors converge
                for i, s1 in enumerate(successors):
                    for s2 in successors[i+1:]:
                        # Trace paths
                        path1 = self._trace_simple_path(s1, max_len=100)
                        path2 = self._trace_simple_path(s2, max_len=100)
                        
                        if path1 and path2 and path1[-1] == path2[-1]:
                            # Bubble found - keep higher coverage path
                            cov1 = sum(self.kmer_coverage.get(n, 0) for n in path1)
                            cov2 = sum(self.kmer_coverage.get(n, 0) for n in path2)
                            
                            if cov1 < cov2:
                                for n in path1[:-1]:
                                    if n in self.graph:
                                        del self.graph[n]
                            else:
                                for n in path2[:-1]:
                                    if n in self.graph:
                                        del self.graph[n]
                            
                            bubbles_removed += 1
        
        self.logger.info(f"Removed {bubbles_removed} bubbles")
    
    def _trace_simple_path(self, start: str, max_len: int = 100) -> Optional[List[str]]:
        """Trace a simple (non-branching) path from start node."""
        path = [start]
        current = start
        
        while len(path) < max_len:
            successors = list(self.graph.get(current, set()))
            
            if len(successors) != 1:
                break
            
            next_node = successors[0]
            if self.in_degree[next_node] != 1:
                path.append(next_node)
                break
            
            path.append(next_node)
            current = next_node
        
        return path if len(path) > 1 else None
    
    def _extract_contigs(self) -> List[Contig]:
        """Extract contigs from simplified graph."""
        contigs = []
        visited = set()
        contig_id = 0
        
        # Find starting nodes (in_degree != out_degree or in_degree > 1 or out_degree > 1)
        start_nodes = []
        for node in self.graph:
            if node not in visited:
                in_d = self.in_degree[node]
                out_d = self.out_degree[node]
                if in_d != 1 or out_d != 1 or in_d == 0:
                    start_nodes.append(node)
        
        # Also add nodes not in any edge source
        all_nodes = set(self.graph.keys())
        for edges in self.graph.values():
            all_nodes.update(edges)
        
        for node in all_nodes:
            if node not in visited and node not in self.graph:
                start_nodes.append(node)
        
        # Extract contigs from each start node
        for start in start_nodes:
            if start in visited:
                continue
            
            path = self._trace_simple_path(start)
            if path:
                # Build contig sequence
                sequence = path[0]
                for node in path[1:]:
                    sequence += node[-1]
                
                # Calculate coverage
                coverage = np.mean([self.kmer_coverage.get(node, 0) for node in path])
                
                contigs.append(Contig(
                    id=f"contig_{contig_id}",
                    sequence=sequence,
                    coverage=coverage,
                ))
                contig_id += 1
                
                visited.update(path)
        
        # Sort by length
        contigs.sort(key=lambda c: c.length, reverse=True)
        
        return contigs
    
    def get_assembly_graph(self) -> "AssemblyGraph":
        """Get the de Bruijn assembly graph."""
        return AssemblyGraph(
            nodes=list(self.graph.keys()),
            edges=[(src, dst) for src, dsts in self.graph.items() for dst in dsts],
            node_coverage=dict(self.kmer_coverage),
        )


class OverlapLayoutConsensus(Assembler):
    """Overlap-Layout-Consensus assembler for long reads."""
    
    def __init__(
        self,
        min_overlap: int = 500,
        min_identity: float = 0.85,
        params: Optional[Dict] = None,
    ):
        super().__init__(params)
        self.min_overlap = min_overlap
        self.min_identity = min_identity
        self.overlaps: List[Tuple] = []
    
    def assemble(self, reads: List[str]) -> AssemblyResult:
        """Assemble reads using OLC approach."""
        self.logger.info(f"OLC assembly with min_overlap={self.min_overlap}")
        
        # Find all overlaps
        self.logger.info("Finding overlaps...")
        self._find_overlaps(reads)
        
        # Build overlap graph
        self.logger.info("Building string graph...")
        layout = self._build_layout(reads)
        
        # Generate consensus
        self.logger.info("Generating consensus...")
        contigs = self._generate_consensus(reads, layout)
        
        return AssemblyResult(
            contigs=contigs,
            parameters={
                'min_overlap': self.min_overlap,
                'min_identity': self.min_identity,
                'algorithm': 'olc',
            },
        )
    
    def _find_overlaps(self, reads: List[str]):
        """Find overlaps between reads using minimizers."""
        self.overlaps = []
        
        # Build minimizer index for acceleration
        k = 15  # Minimizer k-mer size
        w = 5   # Window size
        
        minimizer_index: Dict[str, List[Tuple[int, int]]] = defaultdict(list)
        
        for read_idx, read in enumerate(reads):
            read = read.upper()
            
            # Extract minimizers
            for i in range(len(read) - k - w + 1):
                window_kmers = []
                for j in range(w):
                    kmer = read[i + j:i + j + k]
                    if 'N' not in kmer:
                        window_kmers.append((kmer, i + j))
                
                if window_kmers:
                    minimizer = min(window_kmers, key=lambda x: x[0])
                    minimizer_index[minimizer[0]].append((read_idx, minimizer[1]))
        
        # Find candidate overlaps
        candidates = defaultdict(set)
        for positions in minimizer_index.values():
            if len(positions) > 1 and len(positions) < 100:  # Filter repetitive
                for i, (read1, pos1) in enumerate(positions):
                    for read2, pos2 in positions[i + 1:]:
                        if read1 != read2:
                            candidates[(read1, read2)].add((pos1, pos2))
        
        # Verify overlaps
        for (read1_idx, read2_idx), seed_positions in candidates.items():
            read1 = reads[read1_idx].upper()
            read2 = reads[read2_idx].upper()
            
            # Check suffix-prefix overlap
            overlap = self._find_suffix_prefix_overlap(read1, read2, seed_positions)
            
            if overlap and overlap[2] >= self.min_overlap:
                self.overlaps.append((
                    read1_idx, read2_idx,
                    overlap[0], overlap[1],  # Start positions
                    overlap[2],  # Overlap length
                    overlap[3],  # Identity
                ))
    
    def _find_suffix_prefix_overlap(
        self,
        read1: str,
        read2: str,
        seed_positions: Set[Tuple[int, int]],
    ) -> Optional[Tuple[int, int, int, float]]:
        """Find best suffix-prefix overlap between two reads."""
        best_overlap = None
        best_score = 0
        
        for pos1, pos2 in seed_positions:
            # Estimate overlap region
            # If pos1 is near end of read1 and pos2 is near start of read2
            if pos1 > len(read1) * 0.5 and pos2 < len(read2) * 0.5:
                # Suffix of read1 overlaps prefix of read2
                start1 = max(0, len(read1) - (len(read1) - pos1) - (pos2) - 100)
                
                overlap_len = min(len(read1) - start1, len(read2))
                
                if overlap_len >= self.min_overlap:
                    # Calculate identity
                    suffix = read1[start1:start1 + overlap_len]
                    prefix = read2[:overlap_len]
                    
                    matches = sum(1 for a, b in zip(suffix, prefix) if a == b)
                    identity = matches / overlap_len
                    
                    if identity >= self.min_identity:
                        score = overlap_len * identity
                        if score > best_score:
                            best_score = score
                            best_overlap = (start1, 0, overlap_len, identity)
        
        return best_overlap
    
    def _build_layout(self, reads: List[str]) -> List[List[int]]:
        """Build layout from overlap graph."""
        n = len(reads)
        
        # Build adjacency list
        adj: Dict[int, List[Tuple[int, int, int]]] = defaultdict(list)
        for read1, read2, start1, start2, overlap_len, identity in self.overlaps:
            adj[read1].append((read2, overlap_len, start1))
        
        # Find longest paths using greedy approach
        layouts = []
        used = set()
        
        # Start from reads with no incoming edges
        incoming = set()
        for read1, read2, *_ in self.overlaps:
            incoming.add(read2)
        
        starts = [i for i in range(n) if i not in incoming and i not in used]
        
        for start in starts:
            if start in used:
                continue
            
            path = [start]
            used.add(start)
            current = start
            
            while adj[current]:
                # Find best next read
                best_next = None
                best_score = 0
                
                for next_read, overlap_len, _ in adj[current]:
                    if next_read not in used:
                        if overlap_len > best_score:
                            best_score = overlap_len
                            best_next = next_read
                
                if best_next is None:
                    break
                
                path.append(best_next)
                used.add(best_next)
                current = best_next
            
            if len(path) > 1:
                layouts.append(path)
        
        return layouts
    
    def _generate_consensus(
        self,
        reads: List[str],
        layouts: List[List[int]],
    ) -> List[Contig]:
        """Generate consensus sequences from layouts."""
        contigs = []
        
        for layout_idx, layout in enumerate(layouts):
            if not layout:
                continue
            
            # Start with first read
            consensus = reads[layout[0]]
            
            # Extend with subsequent reads
            for i in range(1, len(layout)):
                read1_idx = layout[i - 1]
                read2_idx = layout[i]
                
                # Find overlap info
                overlap_info = None
                for r1, r2, s1, s2, olen, ident in self.overlaps:
                    if r1 == read1_idx and r2 == read2_idx:
                        overlap_info = (s1, s2, olen)
                        break
                
                if overlap_info:
                    start1, start2, overlap_len = overlap_info
                    # Extend consensus with non-overlapping part of read2
                    consensus += reads[read2_idx][overlap_len:]
            
            contigs.append(Contig(
                id=f"contig_{layout_idx}",
                sequence=consensus,
                coverage=len(layout),
                source_reads=[str(i) for i in layout],
            ))
        
        return contigs
    
    def get_assembly_graph(self) -> "AssemblyGraph":
        """Get the overlap assembly graph."""
        nodes = list(set(o[0] for o in self.overlaps) | set(o[1] for o in self.overlaps))
        edges = [(o[0], o[1]) for o in self.overlaps]
        edge_weights = {(o[0], o[1]): o[4] for o in self.overlaps}  # Overlap length as weight
        
        return AssemblyGraph(
            nodes=[str(n) for n in nodes],
            edges=[(str(e[0]), str(e[1])) for e in edges],
            edge_weights={str(k): v for k, v in edge_weights.items()},
        )


class ReferenceGuidedAssembler(Assembler):
    """Reference-guided assembly for closely related genomes."""
    
    def __init__(
        self,
        reference: str,
        min_mapping_quality: int = 20,
        params: Optional[Dict] = None,
    ):
        super().__init__(params)
        self.reference = reference.upper()
        self.min_mapping_quality = min_mapping_quality
    
    def assemble(self, reads: List[str]) -> AssemblyResult:
        """Assemble reads guided by reference."""
        self.logger.info("Reference-guided assembly")
        
        # Map reads to reference
        self.logger.info("Mapping reads to reference...")
        mappings = self._map_reads(reads)
        
        # Build pileup and call consensus
        self.logger.info("Building consensus...")
        consensus = self._build_consensus(mappings)
        
        # Split at low-coverage regions
        contigs = self._split_at_gaps(consensus)
        
        return AssemblyResult(
            contigs=contigs,
            parameters={
                'reference_length': len(self.reference),
                'algorithm': 'reference_guided',
            },
        )
    
    def _map_reads(self, reads: List[str]) -> List[Tuple[int, str, int]]:
        """Map reads to reference using k-mer seeding."""
        mappings = []
        k = 15
        
        # Build reference k-mer index
        ref_index: Dict[str, List[int]] = defaultdict(list)
        for i in range(len(self.reference) - k + 1):
            kmer = self.reference[i:i + k]
            if 'N' not in kmer:
                ref_index[kmer].append(i)
        
        # Map each read
        for read_idx, read in enumerate(reads):
            read = read.upper()
            
            # Find seed matches
            seed_matches: Dict[int, int] = defaultdict(int)
            
            for i in range(len(read) - k + 1):
                kmer = read[i:i + k]
                if kmer in ref_index:
                    for ref_pos in ref_index[kmer]:
                        # Estimate mapping position
                        map_pos = ref_pos - i
                        if 0 <= map_pos <= len(self.reference) - len(read):
                            seed_matches[map_pos] += 1
            
            if seed_matches:
                # Find best mapping position
                best_pos = max(seed_matches.keys(), key=lambda p: seed_matches[p])
                
                # Verify alignment quality (simple identity check)
                ref_region = self.reference[best_pos:best_pos + len(read)]
                matches = sum(1 for a, b in zip(read, ref_region) if a == b)
                identity = matches / len(read) if len(read) > 0 else 0
                
                if identity > 0.8:  # Minimum identity threshold
                    mappings.append((best_pos, read, read_idx))
        
        return mappings
    
    def _build_consensus(
        self,
        mappings: List[Tuple[int, str, int]],
    ) -> Tuple[str, List[int]]:
        """Build consensus from mapped reads."""
        # Initialize pileup
        pileup: List[Dict[str, int]] = [defaultdict(int) for _ in range(len(self.reference))]
        coverage = [0] * len(self.reference)
        
        # Add reads to pileup
        for pos, read, _ in mappings:
            for i, base in enumerate(read):
                if pos + i < len(self.reference):
                    pileup[pos + i][base] += 1
                    coverage[pos + i] += 1
        
        # Build consensus
        consensus = []
        for i, pile in enumerate(pileup):
            if pile:
                # Take most common base
                best_base = max(pile.keys(), key=lambda b: pile[b])
                consensus.append(best_base)
            else:
                # No coverage - use reference
                consensus.append(self.reference[i])
        
        return ''.join(consensus), coverage
    
    def _split_at_gaps(
        self,
        consensus_data: Tuple[str, List[int]],
        min_coverage: int = 2,
        max_gap: int = 100,
    ) -> List[Contig]:
        """Split consensus at low-coverage regions."""
        consensus, coverage = consensus_data
        contigs = []
        
        start = 0
        in_gap = coverage[0] < min_coverage
        contig_id = 0
        
        for i in range(1, len(coverage)):
            is_low = coverage[i] < min_coverage
            
            if is_low and not in_gap:
                # End of contig
                if i - start >= 200:  # Minimum contig length
                    seq = consensus[start:i]
                    cov = np.mean(coverage[start:i])
                    contigs.append(Contig(
                        id=f"contig_{contig_id}",
                        sequence=seq,
                        coverage=cov,
                    ))
                    contig_id += 1
                in_gap = True
            
            elif not is_low and in_gap:
                # Start of new contig
                start = i
                in_gap = False
        
        # Add last contig
        if not in_gap and len(consensus) - start >= 200:
            seq = consensus[start:]
            cov = np.mean(coverage[start:])
            contigs.append(Contig(
                id=f"contig_{contig_id}",
                sequence=seq,
                coverage=cov,
            ))
        
        return contigs
    
    def get_assembly_graph(self) -> "AssemblyGraph":
        """Reference-guided assembly doesn't have a traditional graph."""
        return AssemblyGraph(nodes=[], edges=[])


class HybridAssembler(Assembler):
    """Hybrid assembler combining short and long reads."""
    
    def __init__(
        self,
        short_read_k: int = 31,
        long_read_min_overlap: int = 500,
        params: Optional[Dict] = None,
    ):
        super().__init__(params)
        self.short_read_k = short_read_k
        self.long_read_min_overlap = long_read_min_overlap
        self.db_assembler = DeBruijnAssembler(k=short_read_k)
        self.olc_assembler = OverlapLayoutConsensus(min_overlap=long_read_min_overlap)
    
    def assemble(
        self,
        reads: List[str],
        long_reads: Optional[List[str]] = None,
    ) -> AssemblyResult:
        """Hybrid assembly using short and long reads."""
        self.logger.info("Hybrid assembly")
        
        # Step 1: Assemble short reads
        self.logger.info("Assembling short reads...")
        short_assembly = self.db_assembler.assemble(reads)
        
        if not long_reads:
            return short_assembly
        
        # Step 2: Use long reads for scaffolding
        self.logger.info("Scaffolding with long reads...")
        scaffolds = self._scaffold_with_long_reads(
            short_assembly.contigs,
            long_reads,
        )
        
        # Step 3: Fill gaps using long reads
        self.logger.info("Filling gaps...")
        final_contigs = self._fill_gaps(scaffolds, long_reads)
        
        return AssemblyResult(
            contigs=final_contigs,
            scaffolds=scaffolds,
            parameters={
                'short_read_k': self.short_read_k,
                'long_read_min_overlap': self.long_read_min_overlap,
                'algorithm': 'hybrid',
            },
        )
    
    def _scaffold_with_long_reads(
        self,
        contigs: List[Contig],
        long_reads: List[str],
    ) -> List["Scaffold"]:
        """Use long reads to order and orient contigs."""
        from .scaffolding import Scaffold, ScaffoldComponent
        
        # Map long reads to contigs
        contig_links: Dict[Tuple[str, str], List[int]] = defaultdict(list)
        
        k = 15
        # Build contig k-mer index
        contig_index: Dict[str, List[Tuple[str, int, str]]] = defaultdict(list)
        
        for contig in contigs:
            for i in range(len(contig.sequence) - k + 1):
                kmer = contig.sequence[i:i + k]
                # Determine if beginning or end of contig
                region = 'start' if i < len(contig.sequence) // 2 else 'end'
                contig_index[kmer].append((contig.id, i, region))
        
        # Find links
        for read in long_reads:
            read = read.upper()
            matches: List[Tuple[str, int, str, int]] = []
            
            for i in range(len(read) - k + 1):
                kmer = read[i:i + k]
                if kmer in contig_index:
                    for contig_id, contig_pos, region in contig_index[kmer]:
                        matches.append((contig_id, contig_pos, region, i))
            
            # Find contig pairs
            if len(matches) >= 2:
                # Sort by read position
                matches.sort(key=lambda x: x[3])
                
                for i in range(len(matches) - 1):
                    c1, p1, r1, rp1 = matches[i]
                    c2, p2, r2, rp2 = matches[i + 1]
                    
                    if c1 != c2:
                        gap_size = rp2 - rp1 - k
                        contig_links[(c1, c2)].append(gap_size)
        
        # Build scaffolds from links
        scaffolds = []
        used_contigs = set()
        scaffold_id = 0
        
        for contig in contigs:
            if contig.id in used_contigs:
                continue
            
            components = [ScaffoldComponent(
                contig_id=contig.id,
                sequence=contig.sequence,
                orientation='+',
                gap_before=0,
            )]
            used_contigs.add(contig.id)
            
            # Extend scaffold
            current = contig.id
            while True:
                best_link = None
                best_support = 0
                
                for (c1, c2), gaps in contig_links.items():
                    if c1 == current and c2 not in used_contigs:
                        if len(gaps) > best_support:
                            best_support = len(gaps)
                            best_link = (c2, int(np.median(gaps)))
                
                if best_link is None or best_support < 2:
                    break
                
                next_contig_id, gap_size = best_link
                next_contig = next((c for c in contigs if c.id == next_contig_id), None)
                
                if next_contig:
                    components.append(ScaffoldComponent(
                        contig_id=next_contig_id,
                        sequence=next_contig.sequence,
                        orientation='+',
                        gap_before=max(0, gap_size),
                    ))
                    used_contigs.add(next_contig_id)
                    current = next_contig_id
                else:
                    break
            
            scaffolds.append(Scaffold(
                id=f"scaffold_{scaffold_id}",
                components=components,
            ))
            scaffold_id += 1
        
        return scaffolds
    
    def _fill_gaps(
        self,
        scaffolds: List["Scaffold"],
        long_reads: List[str],
    ) -> List[Contig]:
        """Fill scaffold gaps using long reads."""
        contigs = []
        
        for scaffold in scaffolds:
            # Build scaffold sequence with gap filling
            sequence_parts = []
            
            for i, component in enumerate(scaffold.components):
                if i > 0 and component.gap_before > 0:
                    # Try to fill gap with long read
                    gap_seq = self._find_gap_sequence(
                        sequence_parts[-1][-100:] if sequence_parts else "",
                        component.sequence[:100],
                        long_reads,
                        component.gap_before,
                    )
                    
                    if gap_seq:
                        sequence_parts.append(gap_seq)
                    else:
                        # Insert N's for unfilled gap
                        sequence_parts.append('N' * component.gap_before)
                
                if component.orientation == '+':
                    sequence_parts.append(component.sequence)
                else:
                    # Reverse complement
                    complement = {'A': 'T', 'T': 'A', 'G': 'C', 'C': 'G', 'N': 'N'}
                    revcomp = ''.join(complement.get(b, 'N') for b in reversed(component.sequence))
                    sequence_parts.append(revcomp)
            
            full_sequence = ''.join(sequence_parts)
            
            contigs.append(Contig(
                id=scaffold.id.replace('scaffold', 'contig'),
                sequence=full_sequence,
                coverage=len(scaffold.components),
            ))
        
        return contigs
    
    def _find_gap_sequence(
        self,
        left_flank: str,
        right_flank: str,
        long_reads: List[str],
        expected_gap: int,
    ) -> Optional[str]:
        """Find sequence to fill gap from long reads."""
        if not left_flank or not right_flank:
            return None
        
        k = 15
        left_kmer = left_flank[-k:] if len(left_flank) >= k else left_flank
        right_kmer = right_flank[:k] if len(right_flank) >= k else right_flank
        
        for read in long_reads:
            read = read.upper()
            
            left_pos = read.find(left_kmer)
            right_pos = read.find(right_kmer)
            
            if left_pos != -1 and right_pos != -1 and left_pos < right_pos:
                gap_seq = read[left_pos + len(left_kmer):right_pos]
                if abs(len(gap_seq) - expected_gap) < expected_gap * 0.5:
                    return gap_seq
        
        return None
    
    def get_assembly_graph(self) -> "AssemblyGraph":
        """Get the de Bruijn graph from short read assembly."""
        return self.db_assembler.get_assembly_graph()


# Type alias
DeNovoAssembler = DeBruijnAssembler


@dataclass
class AssemblyGraph:
    """Assembly graph representation."""
    nodes: List[str]
    edges: List[Tuple[str, str]]
    node_coverage: Dict[str, int] = field(default_factory=dict)
    edge_weights: Dict[str, float] = field(default_factory=dict)
    
    @property
    def num_nodes(self) -> int:
        return len(self.nodes)
    
    @property
    def num_edges(self) -> int:
        return len(self.edges)
    
    def to_gfa(self) -> str:
        """Convert to GFA format."""
        lines = ['H\tVN:Z:1.0']
        
        for node in self.nodes:
            cov = self.node_coverage.get(node, 0)
            lines.append(f"S\t{node}\t*\tRC:i:{cov}")
        
        for src, dst in self.edges:
            lines.append(f"L\t{src}\t+\t{dst}\t+\t0M")
        
        return '\n'.join(lines)

"""Assembly Graph Module.
=====================

Graph data structures for assembly visualization and analysis.
"""

from collections import defaultdict
from dataclasses import dataclass, field

import numpy as np


@dataclass
class GraphNode:
    """Node in assembly graph."""

    id: str
    sequence: str
    coverage: float = 0.0
    length: int = 0

    def __post_init__(self):
        if self.length == 0:
            self.length = len(self.sequence)


@dataclass
class GraphEdge:
    """Edge in assembly graph."""

    source: str
    target: str
    overlap: int = 0
    weight: float = 1.0
    edge_type: str = "overlap"  # overlap, link, hic


@dataclass
class AssemblyGraph:
    """Assembly graph representation."""

    nodes: list[str]
    edges: list[tuple[str, str]]
    node_coverage: dict[str, int] = field(default_factory=dict)
    node_sequences: dict[str, str] = field(default_factory=dict)
    edge_weights: dict[str, float] = field(default_factory=dict)

    @property
    def num_nodes(self) -> int:
        return len(self.nodes)

    @property
    def num_edges(self) -> int:
        return len(self.edges)

    def get_adjacency_list(self) -> dict[str, list[str]]:
        """Get adjacency list representation."""
        adj = defaultdict(list)
        for src, dst in self.edges:
            adj[src].append(dst)
        return dict(adj)

    def get_in_degree(self) -> dict[str, int]:
        """Get in-degree for each node."""
        in_deg = defaultdict(int)
        for _src, dst in self.edges:
            in_deg[dst] += 1
        return dict(in_deg)

    def get_out_degree(self) -> dict[str, int]:
        """Get out-degree for each node."""
        out_deg = defaultdict(int)
        for src, _dst in self.edges:
            out_deg[src] += 1
        return dict(out_deg)

    def find_tips(self, max_length: int = 1000) -> list[str]:
        """Find tip nodes (dead ends)."""
        in_deg = self.get_in_degree()
        out_deg = self.get_out_degree()

        tips = []
        for node in self.nodes:
            node_len = len(self.node_sequences.get(node, ""))
            if node_len <= max_length:
                if (
                    in_deg.get(node, 0) == 1
                    and out_deg.get(node, 0) == 0
                    or in_deg.get(node, 0) == 0
                    and out_deg.get(node, 0) == 1
                ):
                    tips.append(node)

        return tips

    def find_bubbles(self) -> list[tuple[str, str, list[str], list[str]]]:
        """Find bubble structures in graph."""
        adj = self.get_adjacency_list()
        bubbles = []

        for node in self.nodes:
            successors = adj.get(node, [])
            if len(successors) == 2:
                # Potential bubble start
                path1 = self._trace_path(successors[0], adj)
                path2 = self._trace_path(successors[1], adj)

                # Check if paths converge
                if path1 and path2 and path1[-1] == path2[-1]:
                    bubbles.append((node, path1[-1], path1, path2))

        return bubbles

    def _trace_path(
        self,
        start: str,
        adj: dict[str, list[str]],
        max_length: int = 10,
    ) -> list[str] | None:
        """Trace simple path from start node."""
        path = [start]
        current = start

        while len(path) < max_length:
            successors = adj.get(current, [])
            if len(successors) != 1:
                break

            next_node = successors[0]
            path.append(next_node)
            current = next_node

        return path if len(path) > 1 else None

    def to_gfa(self) -> str:
        """Convert to GFA (Graphical Fragment Assembly) format."""
        lines = ["H\tVN:Z:1.0"]

        # Segments
        for node in self.nodes:
            seq = self.node_sequences.get(node, "*")
            cov = self.node_coverage.get(node, 0)
            lines.append(f"S\t{node}\t{seq}\tRC:i:{cov}")

        # Links
        for src, dst in self.edges:
            overlap = self.edge_weights.get(f"{src}-{dst}", 0)
            lines.append(f"L\t{src}\t+\t{dst}\t+\t{int(overlap)}M")

        return "\n".join(lines)

    @classmethod
    def from_gfa(cls, gfa_content: str) -> "AssemblyGraph":
        """Parse GFA format."""
        nodes = []
        edges = []
        node_sequences = {}
        node_coverage = {}
        edge_weights = {}

        for line in gfa_content.strip().split("\n"):
            if not line or line.startswith("#"):
                continue

            parts = line.split("\t")

            if parts[0] == "S":  # Segment
                node_id = parts[1]
                sequence = parts[2] if len(parts) > 2 else "*"

                nodes.append(node_id)
                if sequence != "*":
                    node_sequences[node_id] = sequence

                # Parse optional tags
                for tag in parts[3:]:
                    if tag.startswith("RC:i:"):
                        node_coverage[node_id] = int(tag.split(":")[2])

            elif parts[0] == "L":  # Link
                src = parts[1]
                dst = parts[3]
                edges.append((src, dst))

                # Parse overlap
                if len(parts) > 5:
                    cigar = parts[5]
                    if cigar.endswith("M"):
                        overlap = int(cigar[:-1])
                        edge_weights[f"{src}-{dst}"] = overlap

        return cls(
            nodes=nodes,
            edges=edges,
            node_sequences=node_sequences,
            node_coverage=node_coverage,
            edge_weights=edge_weights,
        )

    def simplify(self) -> "AssemblyGraph":
        """Simplify graph by removing tips and popping bubbles."""
        # Remove tips
        tips = self.find_tips()
        nodes = [n for n in self.nodes if n not in tips]
        edges = [(s, d) for s, d in self.edges if s not in tips and d not in tips]

        return AssemblyGraph(
            nodes=nodes,
            edges=edges,
            node_sequences={k: v for k, v in self.node_sequences.items() if k not in tips},
            node_coverage={k: v for k, v in self.node_coverage.items() if k not in tips},
            edge_weights=self.edge_weights,
        )

    def get_connected_components(self) -> list[set[str]]:
        """Get connected components."""
        # Build undirected adjacency
        adj = defaultdict(set)
        for src, dst in self.edges:
            adj[src].add(dst)
            adj[dst].add(src)

        visited = set()
        components = []

        for node in self.nodes:
            if node in visited:
                continue

            component = set()
            stack = [node]

            while stack:
                current = stack.pop()
                if current in visited:
                    continue

                visited.add(current)
                component.add(current)

                for neighbor in adj.get(current, []):
                    if neighbor not in visited:
                        stack.append(neighbor)

            if component:
                components.append(component)

        return components


class ContigGraph(AssemblyGraph):
    """Specialized graph for contig relationships."""

    def __init__(self, contigs: list["Contig"]):
        nodes = [c.id for c in contigs]
        node_sequences = {c.id: c.sequence for c in contigs}
        node_coverage = {c.id: int(c.coverage) for c in contigs}

        super().__init__(
            nodes=nodes,
            edges=[],
            node_sequences=node_sequences,
            node_coverage=node_coverage,
        )

        self.contigs = {c.id: c for c in contigs}

    def add_overlap_edges(
        self,
        min_overlap: int = 100,
        min_identity: float = 0.95,
    ):
        """Add edges based on sequence overlap."""
        for c1 in self.contigs.values():
            for c2 in self.contigs.values():
                if c1.id >= c2.id:  # Avoid duplicates and self-loops
                    continue

                # Check suffix-prefix overlap
                overlap = self._find_overlap(c1.sequence, c2.sequence, min_overlap)

                if overlap and overlap[2] >= min_identity:
                    self.edges.append((c1.id, c2.id))
                    self.edge_weights[f"{c1.id}-{c2.id}"] = overlap[0]

    def _find_overlap(
        self,
        seq1: str,
        seq2: str,
        min_len: int,
    ) -> tuple[int, int, float] | None:
        """Find overlap between suffix of seq1 and prefix of seq2."""
        max_len = min(len(seq1), len(seq2))

        for overlap_len in range(max_len, min_len - 1, -1):
            suffix = seq1[-overlap_len:]
            prefix = seq2[:overlap_len]

            matches = sum(1 for a, b in zip(suffix, prefix, strict=False) if a == b)
            identity = matches / overlap_len

            if identity >= 0.95:
                return (overlap_len, 0, identity)

        return None

    def add_link_edges(
        self,
        links: list[tuple[str, str, int, int]],  # contig1, contig2, gap_size, support
        min_support: int = 2,
    ):
        """Add edges based on scaffolding links."""
        for c1, c2, gap_size, support in links:
            if support >= min_support:
                if (c1, c2) not in self.edges:
                    self.edges.append((c1, c2))
                self.edge_weights[f"{c1}-{c2}"] = gap_size


class UnitGraph:
    """Unitig graph for assembly."""

    def __init__(self, k: int = 31):
        self.k = k
        self.unitigs: dict[str, str] = {}
        self.edges: list[tuple[str, str]] = []
        self.coverage: dict[str, float] = {}

    def build_from_kmers(self, kmer_counts: dict[str, int], min_count: int = 3):
        """Build unitig graph from k-mer counts."""
        # Filter k-mers
        solid_kmers = {k for k, c in kmer_counts.items() if c >= min_count}

        # Build initial edges
        kmer_graph = defaultdict(set)

        for kmer in solid_kmers:
            prefix = kmer[:-1]
            suffix = kmer[1:]
            kmer_graph[prefix].add(suffix)

        # Compact into unitigs
        unitig_id = 0
        visited = set()

        for kmer in solid_kmers:
            if kmer in visited:
                continue

            # Extend unitig
            unitig = kmer

            # Extend forward
            current_suffix = kmer[1:]
            while True:
                extensions = [
                    s
                    for s in kmer_graph.get(current_suffix, set())
                    if current_suffix + s[-1] not in visited
                ]
                if len(extensions) != 1:
                    break

                next_base = extensions[0][-1]
                unitig += next_base
                visited.add(unitig[-self.k :])
                current_suffix = unitig[-(self.k - 1) :]

            visited.add(kmer)

            # Calculate coverage
            cov = np.mean(
                [
                    kmer_counts.get(unitig[i : i + self.k], 0)
                    for i in range(len(unitig) - self.k + 1)
                ]
            )

            uid = f"unitig_{unitig_id}"
            self.unitigs[uid] = unitig
            self.coverage[uid] = cov
            unitig_id += 1

        # Build edges between unitigs
        self._build_unitig_edges()

    def _build_unitig_edges(self):
        """Build edges between unitigs based on k-1 overlaps."""
        # Build index of unitig ends
        prefix_index = {}
        suffix_index = {}

        for uid, seq in self.unitigs.items():
            prefix = seq[: self.k - 1]
            suffix = seq[-(self.k - 1) :]

            prefix_index[prefix] = uid
            suffix_index[suffix] = uid

        # Find connections
        for uid, seq in self.unitigs.items():
            suffix = seq[-(self.k - 1) :]

            if suffix in prefix_index:
                target = prefix_index[suffix]
                if target != uid:
                    self.edges.append((uid, target))

    def to_assembly_graph(self) -> AssemblyGraph:
        """Convert to AssemblyGraph."""
        return AssemblyGraph(
            nodes=list(self.unitigs.keys()),
            edges=self.edges,
            node_sequences=dict(self.unitigs),
            node_coverage={k: int(v) for k, v in self.coverage.items()},
        )

    def extract_contigs(self) -> list[str]:
        """Extract contigs by walking the graph."""
        adj = defaultdict(list)
        in_deg = defaultdict(int)

        for src, dst in self.edges:
            adj[src].append(dst)
            in_deg[dst] += 1

        contigs = []
        visited = set()

        # Start from nodes with in_degree 0 or out_degree > 1
        starts = [u for u in self.unitigs if in_deg[u] == 0]

        for start in starts:
            if start in visited:
                continue

            path = [start]
            visited.add(start)
            current = start

            while adj.get(current):
                successors = [s for s in adj[current] if s not in visited]
                if len(successors) != 1:
                    break

                next_node = successors[0]
                path.append(next_node)
                visited.add(next_node)
                current = next_node

            # Build contig sequence
            contig = self.unitigs[path[0]]
            for uid in path[1:]:
                contig += self.unitigs[uid][self.k - 1 :]

            contigs.append(contig)

        return contigs

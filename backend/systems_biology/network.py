"""
Biological Network Module
=========================

Network representation and analysis for biological systems.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
from collections import defaultdict
from abc import ABC, abstractmethod
import numpy as np
import logging

logger = logging.getLogger(__name__)


@dataclass
class Node:
    """Network node."""
    id: str
    name: str = ""
    node_type: str = ""
    attributes: Dict = field(default_factory=dict)


@dataclass
class Edge:
    """Network edge."""
    source: str
    target: str
    edge_type: str = ""
    weight: float = 1.0
    directed: bool = True
    attributes: Dict = field(default_factory=dict)


class BiologicalNetwork:
    """Base class for biological networks."""
    
    def __init__(self, name: str = "network"):
        self.name = name
        self.nodes: Dict[str, Node] = {}
        self.edges: List[Edge] = []
        self._adjacency: Dict[str, Set[str]] = defaultdict(set)
        self._reverse_adjacency: Dict[str, Set[str]] = defaultdict(set)
    
    @property
    def num_nodes(self) -> int:
        return len(self.nodes)
    
    @property
    def num_edges(self) -> int:
        return len(self.edges)
    
    def add_node(self, node: Node):
        """Add node to network."""
        self.nodes[node.id] = node
    
    def add_edge(self, edge: Edge):
        """Add edge to network."""
        self.edges.append(edge)
        self._adjacency[edge.source].add(edge.target)
        self._reverse_adjacency[edge.target].add(edge.source)
        
        if not edge.directed:
            self._adjacency[edge.target].add(edge.source)
            self._reverse_adjacency[edge.source].add(edge.target)
    
    def get_neighbors(self, node_id: str) -> Set[str]:
        """Get outgoing neighbors."""
        return self._adjacency.get(node_id, set())
    
    def get_predecessors(self, node_id: str) -> Set[str]:
        """Get incoming neighbors."""
        return self._reverse_adjacency.get(node_id, set())
    
    def degree(self, node_id: str) -> int:
        """Get node degree."""
        return len(self._adjacency.get(node_id, set())) + len(self._reverse_adjacency.get(node_id, set()))
    
    def in_degree(self, node_id: str) -> int:
        """Get in-degree."""
        return len(self._reverse_adjacency.get(node_id, set()))
    
    def out_degree(self, node_id: str) -> int:
        """Get out-degree."""
        return len(self._adjacency.get(node_id, set()))
    
    def get_adjacency_matrix(self) -> Tuple[np.ndarray, List[str]]:
        """Get adjacency matrix."""
        node_list = list(self.nodes.keys())
        node_idx = {n: i for i, n in enumerate(node_list)}
        
        n = len(node_list)
        matrix = np.zeros((n, n))
        
        for edge in self.edges:
            i = node_idx.get(edge.source)
            j = node_idx.get(edge.target)
            if i is not None and j is not None:
                matrix[i, j] = edge.weight
        
        return matrix, node_list
    
    def subnetwork(self, node_ids: Set[str]) -> "BiologicalNetwork":
        """Extract subnetwork."""
        subnet = BiologicalNetwork(name=f"{self.name}_subnet")
        
        for node_id in node_ids:
            if node_id in self.nodes:
                subnet.add_node(self.nodes[node_id])
        
        for edge in self.edges:
            if edge.source in node_ids and edge.target in node_ids:
                subnet.add_edge(edge)
        
        return subnet
    
    def to_sif(self) -> str:
        """Export to SIF format."""
        lines = []
        for edge in self.edges:
            lines.append(f"{edge.source}\t{edge.edge_type or 'interacts'}\t{edge.target}")
        return '\n'.join(lines)
    
    @classmethod
    def from_edgelist(
        cls,
        edges: List[Tuple[str, str]],
        directed: bool = True,
    ) -> "BiologicalNetwork":
        """Create network from edge list."""
        network = cls()
        
        for source, target in edges:
            if source not in network.nodes:
                network.add_node(Node(id=source, name=source))
            if target not in network.nodes:
                network.add_node(Node(id=target, name=target))
            
            network.add_edge(Edge(source=source, target=target, directed=directed))
        
        return network


class ProteinNetwork(BiologicalNetwork):
    """Protein-protein interaction network."""
    
    def __init__(self, name: str = "PPI"):
        super().__init__(name)
    
    def add_interaction(
        self,
        protein1: str,
        protein2: str,
        interaction_type: str = "physical",
        confidence: float = 1.0,
        experimental_method: str = "",
    ):
        """Add protein-protein interaction."""
        # Add proteins as nodes
        for protein in [protein1, protein2]:
            if protein not in self.nodes:
                self.add_node(Node(id=protein, name=protein, node_type="protein"))
        
        # Add interaction as edge
        self.add_edge(Edge(
            source=protein1,
            target=protein2,
            edge_type=interaction_type,
            weight=confidence,
            directed=False,
            attributes={'method': experimental_method},
        ))
    
    def find_complexes(self, min_size: int = 3) -> List[Set[str]]:
        """Find protein complexes using clustering."""
        analyzer = CommunityDetection()
        communities = analyzer.louvain(self)
        
        return [c for c in communities if len(c) >= min_size]


class GeneRegulatoryNetwork(BiologicalNetwork):
    """Gene regulatory network."""
    
    def __init__(self, name: str = "GRN"):
        super().__init__(name)
    
    def add_regulation(
        self,
        regulator: str,
        target: str,
        regulation_type: str = "activation",  # activation, repression
        confidence: float = 1.0,
    ):
        """Add regulatory interaction."""
        # Add genes as nodes
        for gene in [regulator, target]:
            if gene not in self.nodes:
                self.add_node(Node(id=gene, name=gene, node_type="gene"))
        
        # Set edge weight based on regulation type
        weight = confidence if regulation_type == "activation" else -confidence
        
        self.add_edge(Edge(
            source=regulator,
            target=target,
            edge_type=regulation_type,
            weight=weight,
            directed=True,
        ))
    
    def get_regulators(self, gene: str) -> List[Tuple[str, str]]:
        """Get regulators of a gene."""
        regulators = []
        for edge in self.edges:
            if edge.target == gene:
                reg_type = "activator" if edge.weight > 0 else "repressor"
                regulators.append((edge.source, reg_type))
        return regulators
    
    def get_targets(self, regulator: str) -> List[str]:
        """Get targets of a regulator."""
        return list(self.get_neighbors(regulator))


class MetabolicNetwork(BiologicalNetwork):
    """Metabolic network."""
    
    def __init__(self, name: str = "metabolic"):
        super().__init__(name)
        self.reactions: Dict[str, Dict] = {}
    
    def add_reaction(
        self,
        reaction_id: str,
        substrates: List[Tuple[str, float]],  # (metabolite, stoichiometry)
        products: List[Tuple[str, float]],
        enzyme: Optional[str] = None,
        reversible: bool = True,
    ):
        """Add metabolic reaction."""
        self.reactions[reaction_id] = {
            'substrates': substrates,
            'products': products,
            'enzyme': enzyme,
            'reversible': reversible,
        }
        
        # Add metabolites as nodes
        for metabolite, _ in substrates + products:
            if metabolite not in self.nodes:
                self.add_node(Node(id=metabolite, name=metabolite, node_type="metabolite"))
        
        # Add edges
        for substrate, stoich in substrates:
            for product, _ in products:
                self.add_edge(Edge(
                    source=substrate,
                    target=product,
                    edge_type="reaction",
                    weight=stoich,
                    directed=not reversible,
                    attributes={'reaction': reaction_id},
                ))
    
    def get_stoichiometry_matrix(self) -> Tuple[np.ndarray, List[str], List[str]]:
        """Get stoichiometry matrix."""
        metabolites = list(self.nodes.keys())
        reactions = list(self.reactions.keys())
        
        met_idx = {m: i for i, m in enumerate(metabolites)}
        
        S = np.zeros((len(metabolites), len(reactions)))
        
        for j, rxn_id in enumerate(reactions):
            rxn = self.reactions[rxn_id]
            
            for metabolite, stoich in rxn['substrates']:
                i = met_idx.get(metabolite)
                if i is not None:
                    S[i, j] -= stoich
            
            for metabolite, stoich in rxn['products']:
                i = met_idx.get(metabolite)
                if i is not None:
                    S[i, j] += stoich
        
        return S, metabolites, reactions


class SignalingNetwork(BiologicalNetwork):
    """Cell signaling network."""
    
    def __init__(self, name: str = "signaling"):
        super().__init__(name)
    
    def add_signaling_interaction(
        self,
        upstream: str,
        downstream: str,
        interaction_type: str = "phosphorylation",
        effect: str = "activation",
    ):
        """Add signaling interaction."""
        for component in [upstream, downstream]:
            if component not in self.nodes:
                self.add_node(Node(id=component, name=component, node_type="signaling_molecule"))
        
        weight = 1.0 if effect == "activation" else -1.0
        
        self.add_edge(Edge(
            source=upstream,
            target=downstream,
            edge_type=interaction_type,
            weight=weight,
            directed=True,
        ))
    
    def find_paths(
        self,
        source: str,
        target: str,
        max_length: int = 10,
    ) -> List[List[str]]:
        """Find all paths between source and target."""
        paths = []
        
        def dfs(current: str, path: List[str], visited: Set[str]):
            if len(path) > max_length:
                return
            
            if current == target:
                paths.append(path.copy())
                return
            
            for neighbor in self.get_neighbors(current):
                if neighbor not in visited:
                    visited.add(neighbor)
                    path.append(neighbor)
                    dfs(neighbor, path, visited)
                    path.pop()
                    visited.remove(neighbor)
        
        dfs(source, [source], {source})
        return paths


class NetworkAnalyzer:
    """Network topology analysis."""
    
    def __init__(self, network: BiologicalNetwork):
        self.network = network
    
    def degree_distribution(self) -> Dict[int, int]:
        """Calculate degree distribution."""
        degrees = defaultdict(int)
        for node_id in self.network.nodes:
            d = self.network.degree(node_id)
            degrees[d] += 1
        return dict(degrees)
    
    def clustering_coefficient(self, node_id: str) -> float:
        """Calculate local clustering coefficient."""
        neighbors = list(self.network.get_neighbors(node_id))
        k = len(neighbors)
        
        if k < 2:
            return 0.0
        
        # Count edges among neighbors
        edges = 0
        for i, n1 in enumerate(neighbors):
            for n2 in neighbors[i + 1:]:
                if n2 in self.network.get_neighbors(n1):
                    edges += 1
        
        max_edges = k * (k - 1) / 2
        return edges / max_edges if max_edges > 0 else 0.0
    
    def average_clustering(self) -> float:
        """Calculate average clustering coefficient."""
        coefficients = [self.clustering_coefficient(n) for n in self.network.nodes]
        return np.mean(coefficients) if coefficients else 0.0
    
    def betweenness_centrality(self) -> Dict[str, float]:
        """Calculate betweenness centrality."""
        centrality = {n: 0.0 for n in self.network.nodes}
        nodes = list(self.network.nodes.keys())
        
        for source in nodes:
            # BFS for shortest paths
            distances = {source: 0}
            paths = {source: [[source]]}
            queue = [source]
            
            while queue:
                current = queue.pop(0)
                
                for neighbor in self.network.get_neighbors(current):
                    if neighbor not in distances:
                        distances[neighbor] = distances[current] + 1
                        paths[neighbor] = [p + [neighbor] for p in paths[current]]
                        queue.append(neighbor)
                    elif distances[neighbor] == distances[current] + 1:
                        paths[neighbor].extend([p + [neighbor] for p in paths[current]])
            
            # Count paths through each node
            for target in nodes:
                if target == source or target not in paths:
                    continue
                
                for path in paths[target]:
                    for node in path[1:-1]:
                        centrality[node] += 1 / len(paths[target])
        
        # Normalize
        n = len(nodes)
        if n > 2:
            norm = 2 / ((n - 1) * (n - 2))
            centrality = {k: v * norm for k, v in centrality.items()}
        
        return centrality
    
    def pagerank(
        self,
        damping: float = 0.85,
        max_iterations: int = 100,
        tolerance: float = 1e-6,
    ) -> Dict[str, float]:
        """Calculate PageRank."""
        nodes = list(self.network.nodes.keys())
        n = len(nodes)
        
        if n == 0:
            return {}
        
        # Initialize
        pr = {node: 1.0 / n for node in nodes}
        
        for _ in range(max_iterations):
            new_pr = {}
            
            for node in nodes:
                incoming = self.network.get_predecessors(node)
                
                rank_sum = 0.0
                for pred in incoming:
                    out_degree = self.network.out_degree(pred)
                    if out_degree > 0:
                        rank_sum += pr[pred] / out_degree
                
                new_pr[node] = (1 - damping) / n + damping * rank_sum
            
            # Check convergence
            diff = sum(abs(new_pr[n] - pr[n]) for n in nodes)
            pr = new_pr
            
            if diff < tolerance:
                break
        
        return pr
    
    def shortest_path_length(self, source: str, target: str) -> Optional[int]:
        """Find shortest path length."""
        if source == target:
            return 0
        
        visited = {source}
        queue = [(source, 0)]
        
        while queue:
            current, dist = queue.pop(0)
            
            for neighbor in self.network.get_neighbors(current):
                if neighbor == target:
                    return dist + 1
                
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, dist + 1))
        
        return None
    
    def connected_components(self) -> List[Set[str]]:
        """Find connected components."""
        visited = set()
        components = []
        
        for node in self.network.nodes:
            if node in visited:
                continue
            
            component = set()
            queue = [node]
            
            while queue:
                current = queue.pop()
                if current in visited:
                    continue
                
                visited.add(current)
                component.add(current)
                
                for neighbor in self.network.get_neighbors(current):
                    queue.append(neighbor)
                for neighbor in self.network.get_predecessors(current):
                    queue.append(neighbor)
            
            components.append(component)
        
        return components


class CommunityDetection:
    """Community detection algorithms."""
    
    def louvain(self, network: BiologicalNetwork) -> List[Set[str]]:
        """Louvain community detection (simplified)."""
        # Initialize each node in its own community
        communities = {node: i for i, node in enumerate(network.nodes)}
        
        # Iteratively move nodes to improve modularity
        improved = True
        
        while improved:
            improved = False
            
            for node in network.nodes:
                current_community = communities[node]
                best_community = current_community
                best_gain = 0
                
                # Try moving to neighbor communities
                neighbor_communities = set()
                for neighbor in network.get_neighbors(node):
                    neighbor_communities.add(communities[neighbor])
                for neighbor in network.get_predecessors(node):
                    neighbor_communities.add(communities[neighbor])
                
                for new_community in neighbor_communities:
                    if new_community == current_community:
                        continue
                    
                    # Calculate modularity gain (simplified)
                    gain = self._modularity_gain(
                        network, communities, node, new_community
                    )
                    
                    if gain > best_gain:
                        best_gain = gain
                        best_community = new_community
                
                if best_community != current_community:
                    communities[node] = best_community
                    improved = True
        
        # Group nodes by community
        community_nodes = defaultdict(set)
        for node, comm in communities.items():
            community_nodes[comm].add(node)
        
        return list(community_nodes.values())
    
    def _modularity_gain(
        self,
        network: BiologicalNetwork,
        communities: Dict[str, int],
        node: str,
        new_community: int,
    ) -> float:
        """Calculate modularity gain for moving node."""
        # Simplified modularity calculation
        gain = 0.0
        
        for neighbor in network.get_neighbors(node):
            if communities[neighbor] == new_community:
                gain += 1
            if communities[neighbor] == communities[node]:
                gain -= 1
        
        return gain
    
    def spectral_clustering(
        self,
        network: BiologicalNetwork,
        n_clusters: int = 5,
    ) -> List[Set[str]]:
        """Spectral clustering (simplified)."""
        adj_matrix, node_list = network.get_adjacency_matrix()
        
        # Compute Laplacian
        degrees = adj_matrix.sum(axis=1)
        D = np.diag(degrees)
        L = D - adj_matrix
        
        # Compute eigenvectors
        eigenvalues, eigenvectors = np.linalg.eigh(L)
        
        # Use first k eigenvectors for clustering
        k = min(n_clusters, len(node_list))
        features = eigenvectors[:, :k]
        
        # Simple k-means like clustering
        labels = self._kmeans(features, k)
        
        # Group nodes
        communities = defaultdict(set)
        for i, node in enumerate(node_list):
            communities[labels[i]].add(node)
        
        return list(communities.values())
    
    def _kmeans(self, X: np.ndarray, k: int, max_iter: int = 100) -> np.ndarray:
        """Simple k-means clustering."""
        n = X.shape[0]
        
        # Random initialization
        centers_idx = np.random.choice(n, k, replace=False)
        centers = X[centers_idx]
        
        labels = np.zeros(n, dtype=int)
        
        for _ in range(max_iter):
            # Assign points to nearest center
            for i in range(n):
                distances = [np.linalg.norm(X[i] - c) for c in centers]
                labels[i] = np.argmin(distances)
            
            # Update centers
            new_centers = np.zeros_like(centers)
            counts = np.zeros(k)
            
            for i in range(n):
                new_centers[labels[i]] += X[i]
                counts[labels[i]] += 1
            
            for j in range(k):
                if counts[j] > 0:
                    new_centers[j] /= counts[j]
            
            if np.allclose(centers, new_centers):
                break
            
            centers = new_centers
        
        return labels

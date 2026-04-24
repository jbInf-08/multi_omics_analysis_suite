"""Advanced Feature Engineering Module.
===================================

Comprehensive feature engineering for multi-omics data:
- Statistical features (skewness, kurtosis)
- Graph-based features (centrality measures)
- Interaction features (polynomial, pairwise)
- Clustering features (PCA, K-means distances)
"""

import logging
from dataclasses import dataclass
from enum import Enum

import networkx as nx
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.preprocessing import PolynomialFeatures, StandardScaler

logger = logging.getLogger(__name__)


class FeatureType(str, Enum):
    """Types of engineered features."""

    STATISTICAL = "statistical"
    GRAPH = "graph"
    INTERACTION = "interaction"
    CLUSTERING = "clustering"
    DOMAIN = "domain"


@dataclass
class FeatureEngineeringResult:
    """Result from feature engineering pipeline."""

    features: pd.DataFrame
    feature_names: list[str]
    feature_types: dict[str, FeatureType]
    n_original: int
    n_engineered: int
    parameters: dict


class StatisticalFeatureExtractor:
    """Extract statistical features from data.

    Features include:
    - Mean, std, min, max, median
    - Percentiles (25, 75, 90, 95, 99)
    - Skewness and kurtosis
    - Coefficient of variation
    - Range and IQR
    """

    def __init__(
        self,
        include_basic: bool = True,
        include_percentiles: bool = True,
        include_moments: bool = True,
        include_derived: bool = True,
        axis: int = 1,  # 0=columns, 1=rows
    ):
        """Initialize statistical feature extractor.

        Args:
            include_basic: Include mean, std, min, max, median
            include_percentiles: Include percentile features
            include_moments: Include skewness and kurtosis
            include_derived: Include derived features (CV, IQR)
            axis: Axis to compute features along

        """
        self.include_basic = include_basic
        self.include_percentiles = include_percentiles
        self.include_moments = include_moments
        self.include_derived = include_derived
        self.axis = axis

    def fit_transform(self, X: np.ndarray) -> tuple[np.ndarray, list[str]]:
        """Extract statistical features.

        Args:
            X: Input data matrix

        Returns:
            Feature matrix and feature names

        """
        features = []
        names = []

        if self.include_basic:
            features.append(np.mean(X, axis=self.axis, keepdims=True))
            names.append("stat_mean")
            features.append(np.std(X, axis=self.axis, keepdims=True))
            names.append("stat_std")
            features.append(np.min(X, axis=self.axis, keepdims=True))
            names.append("stat_min")
            features.append(np.max(X, axis=self.axis, keepdims=True))
            names.append("stat_max")
            features.append(np.median(X, axis=self.axis, keepdims=True))
            names.append("stat_median")

        if self.include_percentiles:
            for p in [25, 75, 90, 95, 99]:
                features.append(np.percentile(X, p, axis=self.axis, keepdims=True))
                names.append(f"stat_p{p}")

        if self.include_moments:
            # Skewness
            skew = stats.skew(X, axis=self.axis)
            if skew.ndim == 0:
                skew = np.array([skew])
            features.append(skew.reshape(-1, 1) if self.axis == 1 else skew.reshape(1, -1))
            names.append("stat_skewness")

            # Kurtosis
            kurt = stats.kurtosis(X, axis=self.axis)
            if kurt.ndim == 0:
                kurt = np.array([kurt])
            features.append(kurt.reshape(-1, 1) if self.axis == 1 else kurt.reshape(1, -1))
            names.append("stat_kurtosis")

        if self.include_derived:
            # Coefficient of variation
            mean = np.mean(X, axis=self.axis, keepdims=True)
            std = np.std(X, axis=self.axis, keepdims=True)
            cv = np.where(mean != 0, std / np.abs(mean), 0)
            features.append(cv)
            names.append("stat_cv")

            # Range
            range_val = np.max(X, axis=self.axis, keepdims=True) - np.min(
                X, axis=self.axis, keepdims=True
            )
            features.append(range_val)
            names.append("stat_range")

            # IQR
            iqr = np.percentile(X, 75, axis=self.axis, keepdims=True) - np.percentile(
                X, 25, axis=self.axis, keepdims=True
            )
            features.append(iqr)
            names.append("stat_iqr")

        result = np.hstack(features) if self.axis == 1 else np.vstack(features)
        return result, names


class GraphFeatureExtractor:
    """Extract graph-based features from network data.

    Features include:
    - Degree centrality
    - Betweenness centrality
    - Closeness centrality
    - Eigenvector centrality
    - PageRank
    - Clustering coefficient
    - Hub and authority scores
    """

    def __init__(
        self,
        include_degree: bool = True,
        include_betweenness: bool = True,
        include_closeness: bool = True,
        include_eigenvector: bool = True,
        include_pagerank: bool = True,
        include_clustering: bool = True,
        include_hits: bool = False,
        normalize: bool = True,
    ):
        """Initialize graph feature extractor.

        Args:
            include_degree: Include degree centrality
            include_betweenness: Include betweenness centrality
            include_closeness: Include closeness centrality
            include_eigenvector: Include eigenvector centrality
            include_pagerank: Include PageRank
            include_clustering: Include clustering coefficient
            include_hits: Include HITS hub/authority scores
            normalize: Normalize features

        """
        self.include_degree = include_degree
        self.include_betweenness = include_betweenness
        self.include_closeness = include_closeness
        self.include_eigenvector = include_eigenvector
        self.include_pagerank = include_pagerank
        self.include_clustering = include_clustering
        self.include_hits = include_hits
        self.normalize = normalize

    def fit_transform(
        self,
        edge_index: np.ndarray,
        num_nodes: int,
    ) -> tuple[np.ndarray, list[str]]:
        """Extract graph features.

        Args:
            edge_index: Edge index array (2, num_edges)
            num_nodes: Number of nodes in the graph

        Returns:
            Feature matrix (num_nodes, num_features) and feature names

        """
        # Create NetworkX graph
        G = nx.Graph()
        G.add_nodes_from(range(num_nodes))
        edges = list(zip(edge_index[0], edge_index[1], strict=False))
        G.add_edges_from(edges)

        features = []
        names = []

        if self.include_degree:
            degree = dict(G.degree())
            degree_vec = np.array([degree.get(i, 0) for i in range(num_nodes)])
            features.append(degree_vec.reshape(-1, 1))
            names.append("graph_degree")

        if self.include_betweenness:
            try:
                betweenness = nx.betweenness_centrality(G)
                betweenness_vec = np.array([betweenness.get(i, 0) for i in range(num_nodes)])
                features.append(betweenness_vec.reshape(-1, 1))
                names.append("graph_betweenness")
            except:
                features.append(np.zeros((num_nodes, 1)))
                names.append("graph_betweenness")

        if self.include_closeness:
            try:
                closeness = nx.closeness_centrality(G)
                closeness_vec = np.array([closeness.get(i, 0) for i in range(num_nodes)])
                features.append(closeness_vec.reshape(-1, 1))
                names.append("graph_closeness")
            except:
                features.append(np.zeros((num_nodes, 1)))
                names.append("graph_closeness")

        if self.include_eigenvector:
            try:
                eigenvector = nx.eigenvector_centrality_numpy(G)
                eigenvector_vec = np.array([eigenvector.get(i, 0) for i in range(num_nodes)])
                features.append(eigenvector_vec.reshape(-1, 1))
                names.append("graph_eigenvector")
            except:
                features.append(np.zeros((num_nodes, 1)))
                names.append("graph_eigenvector")

        if self.include_pagerank:
            try:
                pagerank = nx.pagerank(G)
                pagerank_vec = np.array([pagerank.get(i, 0) for i in range(num_nodes)])
                features.append(pagerank_vec.reshape(-1, 1))
                names.append("graph_pagerank")
            except:
                features.append(np.zeros((num_nodes, 1)))
                names.append("graph_pagerank")

        if self.include_clustering:
            try:
                clustering = nx.clustering(G)
                clustering_vec = np.array([clustering.get(i, 0) for i in range(num_nodes)])
                features.append(clustering_vec.reshape(-1, 1))
                names.append("graph_clustering")
            except:
                features.append(np.zeros((num_nodes, 1)))
                names.append("graph_clustering")

        if self.include_hits:
            try:
                hubs, authorities = nx.hits(G)
                hubs_vec = np.array([hubs.get(i, 0) for i in range(num_nodes)])
                auth_vec = np.array([authorities.get(i, 0) for i in range(num_nodes)])
                features.append(hubs_vec.reshape(-1, 1))
                names.append("graph_hub")
                features.append(auth_vec.reshape(-1, 1))
                names.append("graph_authority")
            except:
                features.append(np.zeros((num_nodes, 1)))
                names.append("graph_hub")
                features.append(np.zeros((num_nodes, 1)))
                names.append("graph_authority")

        result = np.hstack(features)

        if self.normalize:
            scaler = StandardScaler()
            result = scaler.fit_transform(result)

        return result, names


class InteractionFeatureExtractor:
    """Extract interaction features between variables.

    Features include:
    - Polynomial features
    - Pairwise products
    - Ratios between top features
    """

    def __init__(
        self,
        degree: int = 2,
        interaction_only: bool = True,
        include_bias: bool = False,
        top_k_interactions: int = 50,
    ):
        """Initialize interaction feature extractor.

        Args:
            degree: Polynomial degree
            interaction_only: Only interaction terms (no powers)
            include_bias: Include bias term
            top_k_interactions: Number of top interactions to keep

        """
        self.degree = degree
        self.interaction_only = interaction_only
        self.include_bias = include_bias
        self.top_k_interactions = top_k_interactions
        self.poly = PolynomialFeatures(
            degree=degree,
            interaction_only=interaction_only,
            include_bias=include_bias,
        )

    def fit_transform(
        self,
        X: np.ndarray,
        feature_names: list[str] | None = None,
    ) -> tuple[np.ndarray, list[str]]:
        """Extract interaction features.

        Args:
            X: Input data matrix
            feature_names: Original feature names

        Returns:
            Feature matrix and feature names

        """
        n_features = X.shape[1]

        # Limit features for polynomial expansion
        if n_features > 100:
            # Select top variance features
            variances = np.var(X, axis=0)
            top_indices = np.argsort(-variances)[:100]
            X_subset = X[:, top_indices]

            if feature_names:
                subset_names = [feature_names[i] for i in top_indices]
            else:
                subset_names = [f"f{i}" for i in top_indices]
        else:
            X_subset = X
            subset_names = feature_names or [f"f{i}" for i in range(n_features)]

        # Generate polynomial features
        X_poly = self.poly.fit_transform(X_subset)

        # Get feature names
        poly_names = self.poly.get_feature_names_out(subset_names)

        # Remove original features (keep only interactions)
        if self.interaction_only:
            interaction_mask = [" " in name for name in poly_names]
            X_poly = X_poly[:, interaction_mask]
            poly_names = [n for n, m in zip(poly_names, interaction_mask, strict=False) if m]

        # Select top k by variance
        if X_poly.shape[1] > self.top_k_interactions:
            variances = np.var(X_poly, axis=0)
            top_indices = np.argsort(-variances)[: self.top_k_interactions]
            X_poly = X_poly[:, top_indices]
            poly_names = [poly_names[i] for i in top_indices]

        # Rename features
        poly_names = [f"interact_{name}" for name in poly_names]

        return X_poly, poly_names


class ClusteringFeatureExtractor:
    """Extract clustering-based features.

    Features include:
    - PCA components
    - K-means cluster distances
    - Cluster assignments (one-hot)
    """

    def __init__(
        self,
        n_pca_components: int = 10,
        n_clusters: int = 5,
        include_pca: bool = True,
        include_kmeans_dist: bool = True,
        include_cluster_assignment: bool = False,
    ):
        """Initialize clustering feature extractor.

        Args:
            n_pca_components: Number of PCA components
            n_clusters: Number of K-means clusters
            include_pca: Include PCA features
            include_kmeans_dist: Include distances to cluster centers
            include_cluster_assignment: Include cluster assignment features

        """
        self.n_pca_components = n_pca_components
        self.n_clusters = n_clusters
        self.include_pca = include_pca
        self.include_kmeans_dist = include_kmeans_dist
        self.include_cluster_assignment = include_cluster_assignment

        self.pca = None
        self.kmeans = None
        self.scaler = StandardScaler()

    def fit_transform(self, X: np.ndarray) -> tuple[np.ndarray, list[str]]:
        """Extract clustering features.

        Args:
            X: Input data matrix

        Returns:
            Feature matrix and feature names

        """
        features = []
        names = []

        # Scale data
        X_scaled = self.scaler.fit_transform(X)

        if self.include_pca:
            n_components = min(self.n_pca_components, X.shape[1], X.shape[0])
            self.pca = PCA(n_components=n_components)
            pca_features = self.pca.fit_transform(X_scaled)
            features.append(pca_features)
            names.extend([f"pca_{i}" for i in range(n_components)])

        if self.include_kmeans_dist or self.include_cluster_assignment:
            n_clusters = min(self.n_clusters, X.shape[0])
            self.kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
            self.kmeans.fit(X_scaled)

            if self.include_kmeans_dist:
                # Distances to cluster centers
                distances = self.kmeans.transform(X_scaled)
                features.append(distances)
                names.extend([f"kmeans_dist_{i}" for i in range(n_clusters)])

            if self.include_cluster_assignment:
                # One-hot cluster assignment
                labels = self.kmeans.labels_
                one_hot = np.zeros((X.shape[0], n_clusters))
                one_hot[np.arange(X.shape[0]), labels] = 1
                features.append(one_hot)
                names.extend([f"cluster_{i}" for i in range(n_clusters)])

        result = np.hstack(features)
        return result, names


class AdvancedFeatureEngineer:
    """Comprehensive feature engineering pipeline.

    Combines multiple feature extraction methods into
    a unified pipeline.
    """

    def __init__(
        self,
        # Statistical features
        include_statistical: bool = True,
        stat_include_moments: bool = True,
        # Graph features
        include_graph: bool = False,
        # Interaction features
        include_interactions: bool = True,
        interaction_degree: int = 2,
        top_k_interactions: int = 50,
        # Clustering features
        include_clustering: bool = True,
        n_pca_components: int = 10,
        n_clusters: int = 5,
        # Output
        max_features: int | None = None,
        feature_selection: str = "variance",  # "variance", "correlation", "none"
    ):
        """Initialize advanced feature engineer.

        Args:
            include_statistical: Include statistical features
            stat_include_moments: Include skewness/kurtosis
            include_graph: Include graph features
            include_interactions: Include interaction features
            interaction_degree: Polynomial degree
            top_k_interactions: Max interaction features
            include_clustering: Include clustering features
            n_pca_components: Number of PCA components
            n_clusters: Number of K-means clusters
            max_features: Maximum features to return
            feature_selection: Feature selection method

        """
        self.include_statistical = include_statistical
        self.stat_include_moments = stat_include_moments
        self.include_graph = include_graph
        self.include_interactions = include_interactions
        self.interaction_degree = interaction_degree
        self.top_k_interactions = top_k_interactions
        self.include_clustering = include_clustering
        self.n_pca_components = n_pca_components
        self.n_clusters = n_clusters
        self.max_features = max_features
        self.feature_selection = feature_selection

        # Extractors
        self.stat_extractor = None
        self.graph_extractor = None
        self.interact_extractor = None
        self.cluster_extractor = None

    def fit_transform(
        self,
        X: np.ndarray,
        feature_names: list[str] | None = None,
        edge_index: np.ndarray | None = None,
    ) -> FeatureEngineeringResult:
        """Extract all engineered features.

        Args:
            X: Input data matrix (samples x features)
            feature_names: Original feature names
            edge_index: Edge index for graph features

        Returns:
            FeatureEngineeringResult

        """
        n_original = X.shape[1]
        all_features = [X]
        all_names = list(feature_names or [f"orig_{i}" for i in range(n_original)])
        feature_types = dict.fromkeys(all_names, FeatureType.DOMAIN)

        # Statistical features
        if self.include_statistical:
            self.stat_extractor = StatisticalFeatureExtractor(
                include_moments=self.stat_include_moments
            )
            stat_features, stat_names = self.stat_extractor.fit_transform(X)
            all_features.append(stat_features)
            all_names.extend(stat_names)
            for name in stat_names:
                feature_types[name] = FeatureType.STATISTICAL

        # Graph features
        if self.include_graph and edge_index is not None:
            self.graph_extractor = GraphFeatureExtractor()
            graph_features, graph_names = self.graph_extractor.fit_transform(edge_index, X.shape[0])
            all_features.append(graph_features)
            all_names.extend(graph_names)
            for name in graph_names:
                feature_types[name] = FeatureType.GRAPH

        # Interaction features
        if self.include_interactions:
            self.interact_extractor = InteractionFeatureExtractor(
                degree=self.interaction_degree,
                top_k_interactions=self.top_k_interactions,
            )
            interact_features, interact_names = self.interact_extractor.fit_transform(
                X, feature_names
            )
            all_features.append(interact_features)
            all_names.extend(interact_names)
            for name in interact_names:
                feature_types[name] = FeatureType.INTERACTION

        # Clustering features
        if self.include_clustering:
            self.cluster_extractor = ClusteringFeatureExtractor(
                n_pca_components=self.n_pca_components,
                n_clusters=self.n_clusters,
            )
            cluster_features, cluster_names = self.cluster_extractor.fit_transform(X)
            all_features.append(cluster_features)
            all_names.extend(cluster_names)
            for name in cluster_names:
                feature_types[name] = FeatureType.CLUSTERING

        # Combine features
        combined = np.hstack(all_features)

        # Feature selection if needed
        if self.max_features and combined.shape[1] > self.max_features:
            combined, all_names, feature_types = self._select_features(
                combined, all_names, feature_types
            )

        # Create DataFrame
        df = pd.DataFrame(combined, columns=all_names)

        return FeatureEngineeringResult(
            features=df,
            feature_names=all_names,
            feature_types=feature_types,
            n_original=n_original,
            n_engineered=len(all_names) - n_original,
            parameters={
                "include_statistical": self.include_statistical,
                "include_graph": self.include_graph,
                "include_interactions": self.include_interactions,
                "include_clustering": self.include_clustering,
            },
        )

    def _select_features(
        self,
        X: np.ndarray,
        names: list[str],
        types: dict[str, FeatureType],
    ) -> tuple[np.ndarray, list[str], dict]:
        """Select top features based on method."""
        if self.feature_selection == "variance":
            variances = np.var(X, axis=0)
            top_indices = np.argsort(-variances)[: self.max_features]
        elif self.feature_selection == "correlation":
            # Keep features with low correlation to each other
            # This is a simplified implementation
            top_indices = np.arange(min(self.max_features, X.shape[1]))
        else:
            top_indices = np.arange(min(self.max_features, X.shape[1]))

        selected_names = [names[i] for i in top_indices]
        selected_types = {name: types[name] for name in selected_names}

        return X[:, top_indices], selected_names, selected_types

    def transform(self, X: np.ndarray) -> np.ndarray:
        """Transform new data using fitted extractors."""
        all_features = [X]

        if self.stat_extractor:
            stat_features, _ = self.stat_extractor.fit_transform(X)
            all_features.append(stat_features)

        if self.interact_extractor:
            interact_features, _ = self.interact_extractor.fit_transform(X)
            all_features.append(interact_features)

        if self.cluster_extractor:
            X_scaled = self.cluster_extractor.scaler.transform(X)
            cluster_features = []
            if self.cluster_extractor.pca:
                cluster_features.append(self.cluster_extractor.pca.transform(X_scaled))
            if self.cluster_extractor.kmeans:
                cluster_features.append(self.cluster_extractor.kmeans.transform(X_scaled))
            if cluster_features:
                all_features.append(np.hstack(cluster_features))

        return np.hstack(all_features)

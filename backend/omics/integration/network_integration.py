"""Network-Based Multi-Omics Integration."""

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from scipy.spatial.distance import pdist, squareform
from sklearn.preprocessing import StandardScaler

from backend.omics.base.omics_base import OmicsData


@dataclass
class NetworkResult:
    """Network integration result."""

    fused_network: np.ndarray
    sample_names: list[str]
    individual_networks: dict[str, np.ndarray]
    clusters: np.ndarray | None = None
    metadata: dict[str, Any] = None


class SimilarityNetworkFusion:
    """Similarity Network Fusion (SNF) for multi-omics integration.

    Reference: Wang et al., Nature Methods 2014
    """

    def __init__(
        self,
        k_neighbors: int = 20,
        mu: float = 0.5,
        n_iterations: int = 20,
    ):
        """Initialize SNF.

        Args:
            k_neighbors: Number of neighbors for KNN kernel
            mu: Hyperparameter for kernel
            n_iterations: Number of iterations for fusion

        """
        self.k_neighbors = k_neighbors
        self.mu = mu
        self.n_iterations = n_iterations

    def fuse(self, datasets: dict[str, OmicsData]) -> NetworkResult:
        """Perform Similarity Network Fusion.

        Args:
            datasets: Dict of omics datasets

        Returns:
            NetworkResult with fused network

        """
        # Align samples
        aligned = self._align_samples(datasets)
        sample_names = list(aligned.values())[0].index.tolist()
        n_samples = len(sample_names)

        # Compute similarity networks for each omics
        networks = {}
        for name, df in aligned.items():
            # Standardize
            scaler = StandardScaler()
            X = scaler.fit_transform(df.values)

            # Compute distance matrix
            distances = squareform(pdist(X, metric="euclidean"))

            # Convert to affinity
            affinity = self._compute_affinity(distances)
            networks[name] = affinity

        # Initialize fused networks
        P = {
            name: self._compute_transition_matrix(W, self.k_neighbors)
            for name, W in networks.items()
        }
        S = {
            name: self._compute_kernel_matrix(W, self.k_neighbors, self.mu)
            for name, W in networks.items()
        }

        # Iterative fusion
        omics_names = list(networks.keys())
        n_omics = len(omics_names)

        if n_omics < 2:
            # The cross-diffusion step averages over the *other* networks, so a
            # single input divided by zero and returned an all-NaN matrix. There
            # is nothing to fuse here, so return the one network as-is.
            only = omics_names[0]
            return NetworkResult(
                fused_network=networks[only],
                sample_names=sample_names,
                individual_networks=networks,
                metadata={"n_omics": 1, "fused": False, "omics_types": omics_names},
            )

        for _ in range(self.n_iterations):
            P_new = {}
            for name in omics_names:
                # Average of other networks
                other_sum = np.zeros((n_samples, n_samples))
                for other_name in omics_names:
                    if other_name != name:
                        other_sum += P[other_name]
                other_avg = other_sum / (n_omics - 1)

                # Update
                P_new[name] = S[name] @ other_avg @ S[name].T
                # Normalize
                P_new[name] = P_new[name] / P_new[name].sum(axis=1, keepdims=True)

            P = P_new

        # Final fused network
        fused = np.zeros((n_samples, n_samples))
        for name in omics_names:
            fused += P[name]
        fused /= n_omics

        # Make symmetric
        fused = (fused + fused.T) / 2

        return NetworkResult(
            fused_network=fused,
            sample_names=sample_names,
            individual_networks=networks,
            metadata={
                "method": "snf",
                "k_neighbors": self.k_neighbors,
                "n_iterations": self.n_iterations,
            },
        )

    def _align_samples(self, datasets: dict[str, OmicsData]) -> dict[str, pd.DataFrame]:
        """Align samples across datasets."""
        common_samples = None
        for name, data in datasets.items():
            samples = set(data.sample_names)
            if common_samples is None:
                common_samples = samples
            else:
                common_samples = common_samples.intersection(samples)

        common_samples = sorted(common_samples)

        aligned = {}
        for name, data in datasets.items():
            df = data.data.copy()
            if not isinstance(df.index, pd.Index) or list(df.index) != data.sample_names:
                df.index = data.sample_names
            aligned[name] = df.loc[common_samples]

        return aligned

    def _compute_affinity(self, distances: np.ndarray, sigma: float = None) -> np.ndarray:
        """Compute affinity matrix from distances."""
        if sigma is None:
            sigma = np.mean(distances)
        affinity = np.exp(-(distances**2) / (2 * sigma**2))
        np.fill_diagonal(affinity, 0)
        return affinity

    def _compute_transition_matrix(self, W: np.ndarray, k: int) -> np.ndarray:
        """Compute transition probability matrix."""
        n = W.shape[0]
        P = np.zeros_like(W)

        for i in range(n):
            # Get k nearest neighbors
            neighbors = np.argsort(W[i])[-k - 1 : -1]  # Exclude self
            P[i, neighbors] = W[i, neighbors]
            # Normalize
            if P[i].sum() > 0:
                P[i] /= P[i].sum()

        return P

    def _compute_kernel_matrix(self, W: np.ndarray, k: int, mu: float) -> np.ndarray:
        """Compute kernel matrix for SNF."""
        n = W.shape[0]
        S = np.zeros_like(W)

        for i in range(n):
            neighbors = np.argsort(W[i])[-k - 1 : -1]
            # Local scaling
            mean_dist = np.mean(W[i, neighbors])
            for j in neighbors:
                S[i, j] = np.exp(-W[i, j] ** 2 / (mu * mean_dist))

        # Normalize
        row_sums = S.sum(axis=1, keepdims=True)
        row_sums[row_sums == 0] = 1
        S /= row_sums

        return S


class NetworkIntegrator:
    """General network integration utilities."""

    @staticmethod
    def build_coexpression_network(
        data: OmicsData,
        method: str = "pearson",
        threshold: float = 0.7,
    ) -> np.ndarray:
        """Build co-expression network."""
        df = data.data
        corr = df.corr(method=method)

        # Threshold
        adj = np.abs(corr.values)
        adj[adj < threshold] = 0
        np.fill_diagonal(adj, 0)

        return adj

    @staticmethod
    def build_sample_network(
        data: OmicsData,
        metric: str = "euclidean",
        k_neighbors: int = 10,
    ) -> np.ndarray:
        """Build sample similarity network."""
        X = data.data.values
        distances = squareform(pdist(X, metric=metric))

        # KNN graph
        n = len(data.sample_names)
        adj = np.zeros((n, n))

        for i in range(n):
            neighbors = np.argsort(distances[i])[1 : k_neighbors + 1]
            adj[i, neighbors] = 1
            adj[neighbors, i] = 1

        return adj

    @staticmethod
    def spectral_clustering(
        network: np.ndarray,
        n_clusters: int,
    ) -> np.ndarray:
        """Perform spectral clustering on network."""
        from sklearn.cluster import SpectralClustering

        clustering = SpectralClustering(
            n_clusters=n_clusters,
            affinity="precomputed",
            random_state=42,
        )

        return clustering.fit_predict(network)

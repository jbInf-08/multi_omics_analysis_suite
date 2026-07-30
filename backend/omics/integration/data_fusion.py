"""Multi-Omics Data Fusion Methods."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

from backend.omics.base.omics_base import OmicsData


@dataclass
class FusionResult:
    """Result of multi-omics data fusion."""

    fused_data: np.ndarray
    sample_names: list[str]
    feature_names: list[str]
    method: str
    metadata: dict[str, Any]
    omics_contributions: dict[str, float] | None = None

    def to_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame(self.fused_data, index=self.sample_names, columns=self.feature_names)


class DataFusion(ABC):
    """Abstract base class for data fusion methods."""

    @abstractmethod
    def fit(self, datasets: dict[str, OmicsData], **kwargs) -> "DataFusion":
        """Fit the fusion model."""
        pass

    @abstractmethod
    def transform(self, datasets: dict[str, OmicsData]) -> FusionResult:
        """Transform and fuse datasets."""
        pass

    def fit_transform(self, datasets: dict[str, OmicsData], **kwargs) -> FusionResult:
        """Fit and transform."""
        self.fit(datasets, **kwargs)
        return self.transform(datasets)

    @staticmethod
    def _variance_contributions(blocks: dict[str, np.ndarray]) -> dict[str, float]:
        """Share of total variance carried by each omics block.

        Each block is the matrix for one omics type. The share is that block's
        summed feature variance over the total across blocks, so the values are
        non-negative and sum to 1.

        Note the limitation this carries, which is why callers record the basis
        in ``metadata["contribution_basis"]``: if the blocks have been
        standardised then every feature has unit variance and this reduces to
        each block's share of the feature count, which says nothing about how
        much signal a block carries. Only the PCA-loading attribution below is
        informative in that case.
        """
        per_block = {
            name: float(np.nansum(np.var(arr, axis=0, ddof=0))) for name, arr in blocks.items()
        }
        total = sum(per_block.values())
        if total <= 0:
            # Degenerate input (constant features): fall back to equal shares
            # rather than dividing by zero.
            n = len(per_block) or 1
            # Immutable value, so fromkeys sharing it across keys is safe.
            return dict.fromkeys(per_block, 1.0 / n)
        return {name: value / total for name, value in per_block.items()}

    @staticmethod
    def _pca_block_contributions(pca: PCA, block_widths: dict[str, int]) -> dict[str, float]:
        """Share of retained variance attributable to each omics block.

        ``pca.components_`` is (n_components, n_features) with unit-norm rows, so
        the squared loadings over one block's columns give that block's share of
        a component. Weighting by ``explained_variance_ratio_`` and summing over
        components attributes the retained variance across blocks; the result is
        renormalised so the shares sum to 1.

        Read this as a share of the *retained* variance, not as a free-standing
        importance score. On the leading components a small, strongly-structured
        block will outrank a large noisy one, which is the useful case. Retain
        enough components and a wide block accumulates share simply because it
        holds more total variance -- correct, but a different question. Callers
        should surface the component count and the explained variance next to
        these numbers so they are not over-read.
        """
        loadings = np.asarray(pca.components_) ** 2
        weights = np.asarray(pca.explained_variance_ratio_)

        contributions: dict[str, float] = {}
        start = 0
        for name, width in block_widths.items():
            stop = start + width
            # Per component, this block's share; weighted by that component's
            # share of the retained variance.
            contributions[name] = float(np.sum(loadings[:, start:stop].sum(axis=1) * weights))
            start = stop

        total = sum(contributions.values())
        if total <= 0:
            n = len(contributions) or 1
            return dict.fromkeys(contributions, 1.0 / n)
        return {name: value / total for name, value in contributions.items()}

    def _align_samples(self, datasets: dict[str, OmicsData]) -> dict[str, pd.DataFrame]:
        """Align samples across datasets."""
        # Find common samples
        common_samples = None
        for name, data in datasets.items():
            samples = set(data.sample_names)
            if common_samples is None:
                common_samples = samples
            else:
                common_samples = common_samples.intersection(samples)

        common_samples = sorted(common_samples)

        # Align each dataset
        aligned = {}
        for name, data in datasets.items():
            df = data.data.copy()
            if not isinstance(df.index, pd.Index) or list(df.index) != data.sample_names:
                df.index = data.sample_names
            aligned[name] = df.loc[common_samples]

        return aligned


class EarlyFusion(DataFusion):
    """Early fusion (feature concatenation).

    Concatenates features from multiple omics datasets after normalization.
    """

    def __init__(
        self,
        normalize: bool = True,
        scale: bool = True,
        reduce_dim: int | None = None,
    ):
        self.normalize = normalize
        self.scale = scale
        self.reduce_dim = reduce_dim
        self.scalers: dict[str, StandardScaler] = {}
        self.pca: PCA | None = None

    def fit(self, datasets: dict[str, OmicsData], **kwargs) -> "EarlyFusion":
        """Fit scalers for each dataset."""
        aligned = self._align_samples(datasets)

        if self.scale:
            for name, df in aligned.items():
                scaler = StandardScaler()
                scaler.fit(df.values)
                self.scalers[name] = scaler

        # Fit PCA if dimensionality reduction requested
        if self.reduce_dim:
            concatenated = self._concatenate(aligned, scale=self.scale)
            self.pca = PCA(n_components=self.reduce_dim)
            self.pca.fit(concatenated)

        return self

    def transform(self, datasets: dict[str, OmicsData]) -> FusionResult:
        """Concatenate and transform datasets."""
        aligned = self._align_samples(datasets)

        # Scale if fitted
        if self.scale and self.scalers:
            for name, df in aligned.items():
                if name in self.scalers:
                    aligned[name] = pd.DataFrame(
                        self.scalers[name].transform(df.values),
                        index=df.index,
                        columns=df.columns,
                    )

        # Concatenate
        fused = self._concatenate(aligned, scale=False)
        sample_names = list(aligned.values())[0].index.tolist()

        # Build feature names with omics prefix
        feature_names = []
        for name, df in aligned.items():
            feature_names.extend([f"{name}_{f}" for f in df.columns])

        # Attribute the fused signal back to each omics block. Computed before
        # PCA rewrites the column space, so the block widths still line up with
        # the concatenated matrix.
        block_widths = {name: df.shape[1] for name, df in aligned.items()}
        if self.pca:
            contributions = self._pca_block_contributions(self.pca, block_widths)
            contribution_basis = "pca_loadings"
        else:
            contributions = self._variance_contributions(
                {name: df.values for name, df in aligned.items()}
            )
            # Degenerate when scaling is on: see _variance_contributions.
            contribution_basis = "scaled_variance_share" if self.scale else "variance_share"

        # Apply PCA if fitted
        variance_explained = None
        if self.pca:
            fused = self.pca.transform(fused)
            feature_names = [f"PC{i+1}" for i in range(fused.shape[1])]
            variance_explained = float(np.sum(self.pca.explained_variance_ratio_))

        return FusionResult(
            fused_data=fused,
            sample_names=sample_names,
            feature_names=feature_names,
            method="early_fusion",
            metadata={
                "n_omics": len(datasets),
                "omics_types": list(datasets.keys()),
                "dimensionality_reduced": self.pca is not None,
                "variance_explained": variance_explained,
                "contribution_basis": contribution_basis,
            },
            omics_contributions=contributions,
        )

    def _concatenate(self, aligned: dict[str, pd.DataFrame], scale: bool = True) -> np.ndarray:
        """Concatenate aligned dataframes."""
        arrays = []
        for name, df in aligned.items():
            arr = df.values
            if scale and name in self.scalers:
                arr = self.scalers[name].transform(arr)
            arrays.append(arr)
        return np.hstack(arrays)


class IntermediateFusion(DataFusion):
    """Intermediate fusion using joint dimensionality reduction.

    Methods: PCA, MOFA-like decomposition
    """

    def __init__(
        self,
        method: str = "pca",
        n_components: int = 50,
        random_state: int = 42,
    ):
        self.method = method
        self.n_components = n_components
        self.random_state = random_state
        self.model = None
        self.scalers: dict[str, StandardScaler] = {}

    def fit(self, datasets: dict[str, OmicsData], **kwargs) -> "IntermediateFusion":
        """Fit the intermediate fusion model."""
        aligned = self._align_samples(datasets)

        # Scale each omics
        for name, df in aligned.items():
            scaler = StandardScaler()
            scaler.fit(df.values)
            self.scalers[name] = scaler

        # Concatenate and fit model
        concatenated = np.hstack(
            [self.scalers[name].transform(df.values) for name, df in aligned.items()]
        )

        if self.method == "pca":
            n_comp = min(self.n_components, concatenated.shape[0], concatenated.shape[1])
            self.model = PCA(n_components=n_comp, random_state=self.random_state)
            self.model.fit(concatenated)

        return self

    def transform(self, datasets: dict[str, OmicsData]) -> FusionResult:
        """Transform using the fitted model."""
        aligned = self._align_samples(datasets)
        sample_names = list(aligned.values())[0].index.tolist()

        # Scale and concatenate
        concatenated = np.hstack(
            [self.scalers[name].transform(df.values) for name, df in aligned.items()]
        )

        # Transform
        fused = self.model.transform(concatenated)

        # Attribute the retained variance across the omics blocks. The blocks
        # occupy contiguous column ranges of `concatenated` in `aligned` order.
        block_widths = {name: df.shape[1] for name, df in aligned.items()}
        if hasattr(self.model, "components_"):
            contributions = self._pca_block_contributions(self.model, block_widths)
            contribution_basis = "pca_loadings"
        else:
            contributions = self._variance_contributions(
                {name: self.scalers[name].transform(df.values) for name, df in aligned.items()}
            )
            contribution_basis = "scaled_variance_share"

        per_component = (
            self.model.explained_variance_ratio_.tolist()
            if hasattr(self.model, "explained_variance_ratio_")
            else None
        )

        return FusionResult(
            fused_data=fused,
            sample_names=sample_names,
            feature_names=[f"Factor{i+1}" for i in range(fused.shape[1])],
            method=f"intermediate_{self.method}",
            metadata={
                "n_omics": len(datasets),
                "variance_explained": per_component,
                "total_variance_explained": (float(sum(per_component)) if per_component else None),
                "contribution_basis": contribution_basis,
            },
            omics_contributions=contributions,
        )


class LateFusion(DataFusion):
    """Late fusion using ensemble of omics-specific predictions.

    Combines predictions from models trained on each omics type.
    """

    def __init__(
        self,
        aggregation: str = "mean",
        weights: dict[str, float] | None = None,
    ):
        self.aggregation = aggregation
        self.weights = weights

    def fit(self, datasets: dict[str, OmicsData], **kwargs) -> "LateFusion":
        """No fitting needed for late fusion."""
        return self

    def transform(self, datasets: dict[str, OmicsData]) -> FusionResult:
        """Combine omics-specific signals without pre-trained predictors.

        When only raw matrices are available, each block is scaled and reduced with PCA,
        then latent scores are concatenated (a common multi-view baseline). For true
        late fusion on model outputs, use :meth:`fuse_predictions` instead.
        """
        aligned = self._align_samples(datasets)
        if not aligned:
            return FusionResult(
                fused_data=np.zeros((0, 0)),
                sample_names=[],
                feature_names=[],
                method="late_fusion_raw_proxy",
                metadata={"note": "empty input"},
            )

        sample_names = list(next(iter(aligned.values())).index)
        blocks: list[np.ndarray] = []
        feature_names: list[str] = []

        for name, df in aligned.items():
            X = StandardScaler().fit_transform(df.values.astype(float))
            n_samples, n_feat = X.shape
            k = min(10, n_feat, max(1, n_samples - 1))
            pca = PCA(n_components=k, random_state=42)
            scores = pca.fit_transform(X)
            blocks.append(scores)
            feature_names.extend([f"{name}_LF{i + 1}" for i in range(k)])

        fused = np.hstack(blocks)

        return FusionResult(
            fused_data=fused,
            sample_names=sample_names,
            feature_names=feature_names,
            method="late_fusion_raw_proxy",
            metadata={
                "n_omics": len(datasets),
                "omics_types": list(datasets.keys()),
                "note": (
                    "Per-omics PCA scores concatenated; use fuse_predictions() when "
                    "per-view model outputs exist."
                ),
            },
            omics_contributions=self.weights,
        )

    def fuse_predictions(
        self,
        predictions: dict[str, np.ndarray],
        sample_names: list[str],
    ) -> FusionResult:
        """Fuse predictions from multiple omics models.

        Args:
            predictions: Dict mapping omics name to prediction array
            sample_names: Sample names

        Returns:
            FusionResult with fused predictions

        """
        # Stack predictions
        pred_arrays = list(predictions.values())

        # Apply weights
        if self.weights:
            weighted = []
            for name, pred in predictions.items():
                w = self.weights.get(name, 1.0)
                weighted.append(pred * w)
            pred_arrays = weighted

        # Aggregate
        stacked = np.stack(pred_arrays, axis=-1)

        if self.aggregation == "mean":
            fused = np.mean(stacked, axis=-1)
        elif self.aggregation == "max":
            fused = np.max(stacked, axis=-1)
        elif self.aggregation == "vote":
            # Majority voting (for classification)
            fused = np.apply_along_axis(
                lambda x: np.bincount(x.astype(int)).argmax(),
                axis=-1,
                arr=stacked,
            )
        else:
            fused = np.mean(stacked, axis=-1)

        return FusionResult(
            fused_data=fused.reshape(-1, 1) if len(fused.shape) == 1 else fused,
            sample_names=sample_names,
            feature_names=["prediction"],
            method=f"late_fusion_{self.aggregation}",
            metadata={
                "n_omics": len(predictions),
                "weights": self.weights,
            },
            omics_contributions=self.weights,
        )

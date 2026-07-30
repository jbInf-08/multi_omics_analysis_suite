"""Tests for the per-omics contribution attribution in data fusion.

These exist because the Integration page previously rendered
``Math.random() * 40 + 10`` as an "Omics Contributions" percentage. The point of
these tests is not that a number is produced, but that the number tracks the
signal actually present in each omics block.
"""

import numpy as np
import pandas as pd
import pytest

from backend.omics.base.omics_base import OmicsData
from backend.omics.integration.data_fusion import EarlyFusion, IntermediateFusion

N_SAMPLES = 60


def _block(name: str, n_features: int, rng, scale: float = 1.0) -> OmicsData:
    samples = [f"S{i}" for i in range(N_SAMPLES)]
    columns = [f"{name}_f{i}" for i in range(n_features)]
    frame = pd.DataFrame(
        rng.normal(0.0, scale, size=(N_SAMPLES, n_features)), index=samples, columns=columns
    )
    return OmicsData(
        data=frame, feature_names=columns, sample_names=samples, data_type=name
    )


def _with_shared_signal(block: OmicsData, rng, strength: float, n_cols: int) -> OmicsData:
    """Inject one latent factor into the first n_cols features of a block."""
    factor = rng.normal(0.0, strength, size=N_SAMPLES)
    block.data.iloc[:, :n_cols] = block.data.iloc[:, :n_cols].values + factor[:, None]
    return block


@pytest.fixture
def rng():
    return np.random.default_rng(20260730)


class TestPcaAttribution:
    def test_block_carrying_the_signal_dominates(self, rng):
        """The block holding the latent factor must get the larger share."""
        loud = _with_shared_signal(_block("transcriptomics", 30, rng), rng, strength=5.0, n_cols=10)
        quiet = _block("proteomics", 30, rng)

        result = IntermediateFusion(n_components=5).fit_transform(
            {"transcriptomics": loud, "proteomics": quiet}
        )

        assert result.metadata["contribution_basis"] == "pca_loadings"
        assert result.omics_contributions["transcriptomics"] > result.omics_contributions[
            "proteomics"
        ]

    def test_contributions_sum_to_one(self, rng):
        datasets = {
            "transcriptomics": _block("transcriptomics", 25, rng),
            "proteomics": _block("proteomics", 15, rng),
            "metabolomics": _block("metabolomics", 40, rng),
        }
        result = IntermediateFusion(n_components=6).fit_transform(datasets)

        assert set(result.omics_contributions) == set(datasets)
        assert sum(result.omics_contributions.values()) == pytest.approx(1.0)
        assert all(0.0 <= v <= 1.0 for v in result.omics_contributions.values())

    def test_attribution_is_not_merely_feature_count(self, rng):
        """A small block with strong signal beats a much larger block of noise.

        This is the property a feature-count proxy cannot have, and it is what
        makes the number worth showing. It holds on the leading components,
        where the decomposition is describing structure rather than noise --
        see test_attribution_follows_retained_variance_not_signal_alone for the
        boundary of that claim.
        """
        small_loud = _with_shared_signal(
            _block("proteomics", 10, rng), rng, strength=8.0, n_cols=10
        )
        large_quiet = _block("transcriptomics", 80, rng)

        result = IntermediateFusion(n_components=2).fit_transform(
            {"proteomics": small_loud, "transcriptomics": large_quiet}
        )

        assert result.omics_contributions["proteomics"] > result.omics_contributions[
            "transcriptomics"
        ]

    def test_attribution_follows_retained_variance_not_signal_alone(self, rng):
        """Document what the number actually means, so it is not over-read.

        The share is of *retained* variance. Retain only the leading components
        and a small, strongly-structured block dominates. Keep retaining
        components and an 80-feature noise block legitimately accumulates share,
        because it genuinely holds more total variance. That is correct, not a
        defect, but it means the value is tied to n_components -- so the API
        reports the component count and variance_explained alongside it rather
        than presenting the share as a free-standing "importance".
        """
        small_loud = _with_shared_signal(
            _block("proteomics", 10, rng), rng, strength=8.0, n_cols=10
        )
        large_quiet = _block("transcriptomics", 80, rng)
        datasets = {"proteomics": small_loud, "transcriptomics": large_quiet}

        few = IntermediateFusion(n_components=2).fit_transform(datasets)
        many = IntermediateFusion(n_components=20).fit_transform(datasets)

        assert few.omics_contributions["proteomics"] > 0.5
        assert many.omics_contributions["proteomics"] < 0.5
        # More components retained means more of the total variance explained.
        assert sum(many.metadata["variance_explained"]) > sum(
            few.metadata["variance_explained"]
        )

    def test_stronger_signal_yields_larger_share(self, rng):
        """Contribution should increase monotonically with signal strength."""
        shares = []
        for strength in (1.0, 4.0, 12.0):
            local = np.random.default_rng(7)
            loud = _with_shared_signal(
                _block("transcriptomics", 30, local), local, strength=strength, n_cols=10
            )
            quiet = _block("proteomics", 30, local)
            result = IntermediateFusion(n_components=5).fit_transform(
                {"transcriptomics": loud, "proteomics": quiet}
            )
            shares.append(result.omics_contributions["transcriptomics"])

        assert shares[0] < shares[1] < shares[2]

    def test_deterministic_across_runs(self, rng):
        """Same input must give the same answer -- the old value changed per render."""
        datasets = {
            "transcriptomics": _block("transcriptomics", 20, np.random.default_rng(1)),
            "proteomics": _block("proteomics", 20, np.random.default_rng(2)),
        }
        first = IntermediateFusion(n_components=4).fit_transform(datasets).omics_contributions
        second = IntermediateFusion(n_components=4).fit_transform(datasets).omics_contributions

        assert first == second


class TestEarlyFusion:
    def test_pca_path_reports_loading_basis(self, rng):
        datasets = {
            "transcriptomics": _block("transcriptomics", 20, rng),
            "proteomics": _block("proteomics", 20, rng),
        }
        result = EarlyFusion(reduce_dim=5).fit_transform(datasets)

        assert result.metadata["contribution_basis"] == "pca_loadings"
        assert result.metadata["variance_explained"] is not None
        assert 0.0 < result.metadata["variance_explained"] <= 1.0
        assert sum(result.omics_contributions.values()) == pytest.approx(1.0)

    def test_unreduced_path_is_flagged_as_a_proxy(self, rng):
        """Without PCA over scaled blocks the share is only a feature-count proxy.

        The basis is recorded so callers can decline to present it as a measure
        of signal. Asserted here so the caveat cannot be dropped silently.
        """
        datasets = {
            "transcriptomics": _block("transcriptomics", 30, rng),
            "proteomics": _block("proteomics", 30, rng),
        }
        result = EarlyFusion(reduce_dim=None).fit_transform(datasets)

        assert result.metadata["contribution_basis"] == "scaled_variance_share"
        # Equal widths, standardised -> exactly equal shares, carrying no signal
        # information whatsoever.
        assert result.omics_contributions["transcriptomics"] == pytest.approx(0.5)


class TestDegenerateInputs:
    def test_constant_features_do_not_divide_by_zero(self):
        samples = [f"S{i}" for i in range(10)]
        flat = pd.DataFrame(
            np.zeros((10, 4)), index=samples, columns=[f"c{i}" for i in range(4)]
        )
        block = OmicsData(
            data=flat,
            feature_names=list(flat.columns),
            sample_names=samples,
            data_type="proteomics",
        )
        contributions = EarlyFusion._variance_contributions(
            {"a": block.data.values, "b": block.data.values}
        )

        assert contributions == {"a": pytest.approx(0.5), "b": pytest.approx(0.5)}

    def test_samples_are_intersected_across_blocks(self, rng):
        """Only samples present in every block are integrated."""
        a = _block("transcriptomics", 10, rng)
        b = _block("proteomics", 10, rng)
        b.sample_names = [f"S{i}" for i in range(20, 20 + N_SAMPLES)]
        b.data.index = b.sample_names

        result = IntermediateFusion(n_components=3).fit_transform(
            {"transcriptomics": a, "proteomics": b}
        )

        # S20..S59 overlap -> 40 shared samples.
        assert result.fused_data.shape[0] == 40
        assert len(result.sample_names) == 40

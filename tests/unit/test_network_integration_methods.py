"""Tests for the network-based integration methods behind /omics/integrate.

snf and network_integration produce a samples x samples similarity matrix
rather than a sample x component matrix, so there is no variance to explain and
no per-omics attribution that holds up. These tests pin down what these methods
do report, and record why the attribution is deliberately absent.
"""

import asyncio
from types import SimpleNamespace
from uuid import uuid4

import numpy as np
import pandas as pd
import pytest

from backend.app.api.v1.routes import omics as routes
from backend.omics.base.omics_base import OmicsData

N_SAMPLES = 50
SAMPLES = [f"S{i}" for i in range(N_SAMPLES)]


def _block(name: str, n_features: int, seed: int, signal: float = 0.0) -> OmicsData:
    rng = np.random.default_rng(seed)
    values = rng.normal(0.0, 1.0, size=(N_SAMPLES, n_features))
    if signal:
        factor = np.random.default_rng(7).normal(0.0, signal, size=N_SAMPLES)
        values += factor[:, None]
    columns = [f"{name}_{i}" for i in range(n_features)]
    return OmicsData(
        data=pd.DataFrame(values, index=SAMPLES, columns=columns),
        feature_names=columns,
        sample_names=SAMPLES,
        data_type=name,
    )


def _by_key():
    return {
        "a": SimpleNamespace(id=uuid4(), name="RNA-seq", omics_type="transcriptomics"),
        "b": SimpleNamespace(id=uuid4(), name="Proteome", omics_type="proteomics"),
    }


def _run(method: str, inputs: dict, pathway_file: str | None = None):
    body = routes.OmicsIntegrationRequest(
        project_id=uuid4(),
        dataset_ids=[uuid4(), uuid4()],
        method=method,
        pathway_file=pathway_file,
    )
    handler = (
        routes._integrate_by_pathway
        if method == "pathway_integration"
        else routes._integrate_by_network
    )
    return asyncio.run(handler(body, inputs, _by_key(), 35))


@pytest.mark.parametrize("method", ["snf", "network_integration"])
class TestNetworkMethods:
    def test_returns_one_point_per_shared_sample(self, method):
        inputs = {"a": _block("tx", 20, 1, signal=4.0), "b": _block("pr", 15, 2)}
        result = _run(method, inputs)

        assert result.n_samples == N_SAMPLES
        assert len(result.embedding) == N_SAMPLES
        assert {p.sample for p in result.embedding} == set(SAMPLES)

    def test_reports_no_variance_explained(self, method):
        """A similarity network has no decomposition, so there is none to report."""
        inputs = {"a": _block("tx", 20, 1, signal=4.0), "b": _block("pr", 15, 2)}
        result = _run(method, inputs)

        assert result.variance_explained is None
        assert result.contribution_basis == "not_applicable"

    def test_deterministic(self, method):
        inputs = {"a": _block("tx", 20, 1, signal=4.0), "b": _block("pr", 15, 2)}
        first = [(p.x, p.y, p.cluster) for p in _run(method, inputs).embedding]
        second = [(p.x, p.y, p.cluster) for p in _run(method, inputs).embedding]
        assert first == second


class TestNoContributionIsReported:
    """Network methods deliberately report no per-omics attribution.

    The obvious candidate -- correlating each input network against the fused
    one -- did not hold up: the same pure-noise block moved from a 0.00 share to
    a 0.44 share purely by changing its feature count from 15 to 20, because SNF
    iterates the inputs toward one another. Rather than render a bar chart from
    that, nothing is reported and the basis says so.
    """

    def test_contributions_are_empty(self):
        inputs = {"a": _block("tx", 20, 1, signal=5.0), "b": _block("pr", 20, 2)}
        result = _run("snf", inputs)

        assert result.contributions == []
        assert result.contribution_basis == "not_applicable"

    def test_the_rest_of_the_result_is_still_computed(self):
        """Dropping the attribution must not cost the parts that are sound."""
        inputs = {"a": _block("tx", 20, 1, signal=5.0), "b": _block("pr", 20, 2)}
        result = _run("snf", inputs)

        assert result.n_samples == N_SAMPLES
        assert result.n_omics == 2
        assert len(result.embedding) == N_SAMPLES
        assert result.n_clusters >= 1


class TestSnfSingleInput:
    def test_one_dataset_does_not_produce_nan(self):
        """The cross-diffusion step averaged over the *other* networks, so a
        single input divided by zero and returned an all-NaN matrix."""
        from backend.omics.integration.network_integration import SimilarityNetworkFusion

        result = SimilarityNetworkFusion().fuse({"a": _block("tx", 20, 1, signal=3.0)})

        assert np.all(np.isfinite(result.fused_network))
        assert result.metadata["fused"] is False
        assert result.fused_network.shape == (N_SAMPLES, N_SAMPLES)


class TestPathwayIntegration:
    def test_refuses_to_run_without_pathway_definitions(self):
        """The built-in sets are eight toy gene sets; scoring against them would
        produce numbers that look like results and are not."""
        from fastapi import HTTPException

        inputs = {"a": _block("tx", 20, 1), "b": _block("pr", 15, 2)}
        with pytest.raises(HTTPException) as excinfo:
            _run("pathway_integration", inputs)

        assert excinfo.value.status_code == 400
        assert "pathway_file" in excinfo.value.detail

    def test_reports_a_missing_pathway_file_clearly(self):
        from fastapi import HTTPException

        inputs = {"a": _block("tx", 20, 1), "b": _block("pr", 15, 2)}
        with pytest.raises(HTTPException) as excinfo:
            _run("pathway_integration", inputs, pathway_file="/no/such/file.gmt")

        assert excinfo.value.status_code == 400
        assert "not found" in excinfo.value.detail.lower()


class TestSpectralHelpers:
    def test_coordinates_are_finite_for_every_sample(self):
        rng = np.random.default_rng(3)
        affinity = np.abs(rng.normal(size=(20, 20)))
        affinity = (affinity + affinity.T) / 2

        coords = routes._spectral_coordinates(affinity)

        assert coords.shape == (20, 2)
        assert np.all(np.isfinite(coords))

    def test_tiny_inputs_do_not_raise(self):
        coords = routes._spectral_coordinates(np.ones((2, 2)))
        assert coords.shape == (2, 2)

        k, labels = routes._cluster_network(np.ones((2, 2)))
        assert k == 1
        assert labels == [0, 0]

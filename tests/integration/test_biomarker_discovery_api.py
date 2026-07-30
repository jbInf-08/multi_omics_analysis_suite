"""Integration tests for POST /api/v1/biomarkers/discover.

The fixtures plant a known answer: a fixed set of features is shifted between
the two outcome groups and the rest is noise, so the planted features are the
ones that must come back.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import numpy as np
import pandas as pd
import pytest

from backend.app.core.security import TokenPayload, get_current_user
from backend.app.main import app

N_PER_GROUP = 30
N_SAMPLES = N_PER_GROUP * 2
SAMPLES = [f"S{i}" for i in range(N_SAMPLES)]
GROUPS = ["responder"] * N_PER_GROUP + ["non_responder"] * N_PER_GROUP
#: Features deliberately shifted between the groups; everything else is noise.
PLANTED = ["rna_0", "rna_1", "rna_2"]


def _token(sub: str) -> TokenPayload:
    now = datetime.now(timezone.utc)
    return TokenPayload(sub=sub, exp=now + timedelta(hours=1), iat=now, type="access")


@pytest.fixture
def project():
    proj = MagicMock()
    proj.id = uuid4()
    proj.owner_id = uuid4()
    return proj


@pytest.fixture
def auth_as_owner(project):
    async def _user():
        return _token(str(project.owner_id))

    app.dependency_overrides[get_current_user] = _user
    yield
    app.dependency_overrides.pop(get_current_user, None)


def _dataset(project_id, name, omics_type, path, sample_metadata=None):
    ds = MagicMock()
    ds.id = uuid4()
    ds.name = name
    ds.omics_type = omics_type
    ds.storage_path = path
    ds.project_id = project_id
    ds.sample_metadata = sample_metadata
    return ds


def _returns(session_mock, project, datasets):
    project_result = MagicMock()
    project_result.scalar_one_or_none = MagicMock(return_value=project)
    scalars = MagicMock()
    scalars.all = MagicMock(return_value=datasets)
    dataset_result = MagicMock()
    dataset_result.scalars = MagicMock(return_value=scalars)
    session_mock.execute = AsyncMock(side_effect=[project_result, dataset_result])


def _write(tmp_path, name, prefix, n_features, seed, with_outcome=False, planted=()):
    """Matrix where `planted` columns are shifted between the two groups."""
    rng = np.random.default_rng(seed)
    values = rng.normal(10.0, 1.0, size=(N_SAMPLES, n_features))
    columns = [f"{prefix}_{i}" for i in range(n_features)]
    for feature in planted:
        idx = columns.index(feature)
        # Baseline mean is 10, so +20 gives a 3x change: log2FC ~= 1.58, above
        # the project's 1.0 threshold. A smaller shift would be significant by
        # p-value yet correctly filtered out on effect size.
        values[N_PER_GROUP:, idx] += 20.0
    frame = pd.DataFrame(values, index=SAMPLES, columns=columns)
    if with_outcome:
        frame["response"] = GROUPS
    path = tmp_path / f"{name}.parquet"
    frame.to_parquet(path)
    return str(path)


def _payload(project, datasets, **overrides):
    body = {
        "project_id": str(project.id),
        "dataset_ids": [str(d.id) for d in datasets],
        "analysis_type": "differential",
        "outcome_column": "response",
        "groups": ["responder", "non_responder"],
        "feature_selection": "random_forest",
        "cv_folds": 5,
    }
    body.update(overrides)
    return body


class TestValidation:
    def test_rejects_unknown_analysis_type(
        self, test_client, auth_headers, db_override, project, auth_as_owner
    ):
        ds = _dataset(project.id, "a", "transcriptomics", "x")
        response = test_client.post(
            "/api/v1/biomarkers/discover",
            headers=auth_headers,
            json=_payload(project, [ds], analysis_type="astrology"),
        )
        assert response.status_code == 400
        assert "analysis_type" in response.json()["detail"]

    def test_rejects_unknown_selection_method(
        self, test_client, auth_headers, db_override, project, auth_as_owner
    ):
        ds = _dataset(project.id, "a", "transcriptomics", "x")
        response = test_client.post(
            "/api/v1/biomarkers/discover",
            headers=auth_headers,
            json=_payload(project, [ds], feature_selection="vibes"),
        )
        assert response.status_code == 400

    def test_rejects_unsupported_cv(
        self, test_client, auth_headers, db_override, project, auth_as_owner
    ):
        ds = _dataset(project.id, "a", "transcriptomics", "x")
        response = test_client.post(
            "/api/v1/biomarkers/discover",
            headers=auth_headers,
            json=_payload(project, [ds], cv_folds=7),
        )
        assert response.status_code == 400

    def test_missing_outcome_column_is_refused(
        self, test_client, auth_headers, db_override, project, auth_as_owner, tmp_path
    ):
        """Without an outcome there is nothing to discover against."""
        path = _write(tmp_path, "rna", "rna", 20, seed=1)
        ds = _dataset(project.id, "RNA", "transcriptomics", path)
        _returns(db_override, project, [ds])

        response = test_client.post(
            "/api/v1/biomarkers/discover",
            headers=auth_headers,
            json=_payload(project, [ds], outcome_column="no_such_column"),
        )
        assert response.status_code == 400
        assert "no_such_column" in response.json()["detail"]

    def test_more_than_two_groups_needs_an_explicit_pair(
        self, test_client, auth_headers, db_override, project, auth_as_owner, tmp_path
    ):
        rng = np.random.default_rng(5)
        frame = pd.DataFrame(
            rng.normal(size=(N_SAMPLES, 10)),
            index=SAMPLES,
            columns=[f"rna_{i}" for i in range(10)],
        )
        frame["response"] = ["a", "b", "c"] * (N_SAMPLES // 3)
        path = tmp_path / "multi.parquet"
        frame.to_parquet(path)
        ds = _dataset(project.id, "RNA", "transcriptomics", str(path))
        _returns(db_override, project, [ds])

        response = test_client.post(
            "/api/v1/biomarkers/discover",
            headers=auth_headers,
            json=_payload(project, [ds], groups=None),
        )
        assert response.status_code == 400
        assert "exactly two" in response.json()["detail"].lower()


class TestDiscovery:
    def test_recovers_the_planted_features(
        self, test_client, auth_headers, db_override, project, auth_as_owner, tmp_path
    ):
        """The three shifted features must come back; noise must not swamp them."""
        path = _write(tmp_path, "rna", "rna", 25, seed=1, with_outcome=True, planted=PLANTED)
        ds = _dataset(project.id, "RNA-seq", "transcriptomics", path)
        _returns(db_override, project, [ds])

        response = test_client.post(
            "/api/v1/biomarkers/discover",
            headers=auth_headers,
            json=_payload(project, [ds]),
        )

        assert response.status_code == 200, response.text
        body = response.json()

        assert body["n_samples"] == N_SAMPLES
        assert body["outcome_groups"] == ["responder", "non_responder"]
        found = {b["feature"] for b in body["biomarkers"]}
        assert set(PLANTED).issubset(found), f"planted features missing: {found}"

    def test_a_biomarker_carries_both_kinds_of_evidence(
        self, test_client, auth_headers, db_override, project, auth_as_owner, tmp_path
    ):
        """Significance and selection, not one or the other."""
        path = _write(tmp_path, "rna", "rna", 25, seed=1, with_outcome=True, planted=PLANTED)
        ds = _dataset(project.id, "RNA-seq", "transcriptomics", path)
        _returns(db_override, project, [ds])

        body = test_client.post(
            "/api/v1/biomarkers/discover", headers=auth_headers, json=_payload(project, [ds])
        ).json()

        top = body["biomarkers"][0]
        assert top["q_value"] <= body["fdr_threshold"]
        assert abs(top["effect"]) >= 1.0
        assert top["selection_score"] > 0.0
        # The intersection can only be as large as either side.
        assert len(body["biomarkers"]) <= min(body["n_significant"], body["n_selected"])

    def test_reports_which_dataset_each_biomarker_came_from(
        self, test_client, auth_headers, db_override, project, auth_as_owner, tmp_path
    ):
        """The point of multi-omics discovery: provenance per feature."""
        rna = _write(tmp_path, "rna", "rna", 20, seed=1, with_outcome=True, planted=PLANTED)
        prot = _write(tmp_path, "prot", "prot", 15, seed=2)
        a = _dataset(project.id, "RNA-seq", "transcriptomics", rna)
        b = _dataset(project.id, "Proteome", "proteomics", prot)
        _returns(db_override, project, [a, b])

        body = test_client.post(
            "/api/v1/biomarkers/discover",
            headers=auth_headers,
            json=_payload(project, [a, b]),
        ).json()

        assert body["biomarkers"], body.get("notes")
        for marker in body["biomarkers"]:
            assert marker["dataset_name"] in {"RNA-seq", "Proteome"}
            assert marker["omics_type"] in {"transcriptomics", "proteomics"}
        # The planted signal is in the RNA block, so that is where they come from.
        planted_sources = {m["dataset_name"] for m in body["biomarkers"] if m["feature"] in PLANTED}
        assert planted_sources == {"RNA-seq"}

    def test_reports_cross_validated_performance_with_its_caveat(
        self, test_client, auth_headers, db_override, project, auth_as_owner, tmp_path
    ):
        path = _write(tmp_path, "rna", "rna", 25, seed=1, with_outcome=True, planted=PLANTED)
        ds = _dataset(project.id, "RNA-seq", "transcriptomics", path)
        _returns(db_override, project, [ds])

        body = test_client.post(
            "/api/v1/biomarkers/discover", headers=auth_headers, json=_payload(project, [ds])
        ).json()

        assert body["validation"] is not None
        assert body["validation"]["metric"] == "roc_auc"
        assert body["validation"]["folds"] == 5
        # A clearly separable planted signal should score well.
        assert body["validation"]["score"] > 0.8
        # And the caveat about selecting on all samples must travel with it.
        assert any("generalisation" in n for n in body["notes"])

    def test_pure_noise_yields_no_biomarkers_and_says_so(
        self, test_client, auth_headers, db_override, project, auth_as_owner, tmp_path
    ):
        """Nothing planted, so nothing should be reported."""
        path = _write(tmp_path, "rna", "rna", 25, seed=9, with_outcome=True)
        ds = _dataset(project.id, "RNA-seq", "transcriptomics", path)
        _returns(db_override, project, [ds])

        body = test_client.post(
            "/api/v1/biomarkers/discover", headers=auth_headers, json=_payload(project, [ds])
        ).json()

        assert body["biomarkers"] == []
        assert body["n_significant"] == 0
        assert body["notes"]

    def test_outcome_can_come_from_sample_metadata(
        self, test_client, auth_headers, db_override, project, auth_as_owner, tmp_path
    ):
        """Matches how run_differential_expression resolves its group column."""
        path = _write(tmp_path, "rna", "rna", 25, seed=1, planted=PLANTED)
        metadata = {s: {"response": g} for s, g in zip(SAMPLES, GROUPS, strict=False)}
        ds = _dataset(project.id, "RNA-seq", "transcriptomics", path, sample_metadata=metadata)
        _returns(db_override, project, [ds])

        response = test_client.post(
            "/api/v1/biomarkers/discover", headers=auth_headers, json=_payload(project, [ds])
        )

        assert response.status_code == 200, response.text
        assert response.json()["n_samples"] == N_SAMPLES

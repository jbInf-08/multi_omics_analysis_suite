"""Integration tests for POST /api/v1/omics/integrate.

The Integration page used to display fabricated numbers: a 3s setTimeout stood
in for the analysis and the "Omics Contributions" percentages were
``Math.random()``. These tests cover the endpoint that replaced that, including
one end-to-end run over real parquet files whose expected answer is known from
how the fixtures are constructed.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import numpy as np
import pandas as pd
import pytest

from backend.app.core.security import TokenPayload, get_current_user
from backend.app.main import app

N_SAMPLES = 40


def _token_payload(sub: str) -> TokenPayload:
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
        return _token_payload(str(project.owner_id))

    app.dependency_overrides[get_current_user] = _user
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def auth_as_intruder():
    async def _user():
        return _token_payload(str(uuid4()))

    app.dependency_overrides[get_current_user] = _user
    yield
    app.dependency_overrides.pop(get_current_user, None)


def _dataset(project_id, name, omics_type, storage_path):
    ds = MagicMock()
    ds.id = uuid4()
    ds.name = name
    ds.omics_type = omics_type
    ds.storage_path = storage_path
    ds.project_id = project_id
    return ds


def _returns(session_mock, project, datasets):
    """First execute() resolves the project, the second the dataset rows."""
    project_result = MagicMock()
    project_result.scalar_one_or_none = MagicMock(return_value=project)

    scalars = MagicMock()
    scalars.all = MagicMock(return_value=datasets)
    dataset_result = MagicMock()
    dataset_result.scalars = MagicMock(return_value=scalars)

    session_mock.execute = AsyncMock(side_effect=[project_result, dataset_result])


def _write_parquet(tmp_path, name, n_features, seed, signal_strength=0.0):
    """Write a samples x features matrix; optionally inject a shared factor."""
    rng = np.random.default_rng(seed)
    samples = [f"S{i}" for i in range(N_SAMPLES)]
    columns = [f"{name}_f{i}" for i in range(n_features)]
    values = rng.normal(0.0, 1.0, size=(N_SAMPLES, n_features))
    if signal_strength:
        factor = np.random.default_rng(99).normal(0.0, signal_strength, size=N_SAMPLES)
        values += factor[:, None]
    frame = pd.DataFrame(values, index=samples, columns=columns)
    path = tmp_path / f"{name}.parquet"
    frame.to_parquet(path)
    return str(path)


class TestValidation:
    def test_rejects_a_single_dataset(self, test_client, auth_headers, db_override):
        response = test_client.post(
            "/api/v1/omics/integrate",
            headers=auth_headers,
            json={
                "project_id": str(uuid4()),
                "dataset_ids": [str(uuid4())],
                "method": "intermediate_fusion",
            },
        )
        assert response.status_code == 422

    def test_rejects_unimplemented_method(
        self, test_client, auth_headers, db_override, project, auth_as_owner
    ):
        response = test_client.post(
            "/api/v1/omics/integrate",
            headers=auth_headers,
            json={
                "project_id": str(project.id),
                "dataset_ids": [str(uuid4()), str(uuid4())],
                "method": "not_a_real_method",
            },
        )
        assert response.status_code == 400
        assert "not implemented" in response.json()["detail"]

    def test_missing_project_is_404(self, test_client, auth_headers, db_override, auth_as_owner):
        _returns(db_override, None, [])
        response = test_client.post(
            "/api/v1/omics/integrate",
            headers=auth_headers,
            json={
                "project_id": str(uuid4()),
                "dataset_ids": [str(uuid4()), str(uuid4())],
                "method": "intermediate_fusion",
            },
        )
        assert response.status_code == 404

    def test_other_users_project_is_403(
        self, test_client, auth_headers, db_override, project, auth_as_intruder
    ):
        _returns(db_override, project, [])
        response = test_client.post(
            "/api/v1/omics/integrate",
            headers=auth_headers,
            json={
                "project_id": str(project.id),
                "dataset_ids": [str(uuid4()), str(uuid4())],
                "method": "intermediate_fusion",
            },
        )
        assert response.status_code == 403

    def test_dataset_without_stored_data_is_409(
        self, test_client, auth_headers, db_override, project, auth_as_owner
    ):
        a = _dataset(project.id, "rna", "transcriptomics", None)
        b = _dataset(project.id, "prot", "proteomics", None)
        _returns(db_override, project, [a, b])

        response = test_client.post(
            "/api/v1/omics/integrate",
            headers=auth_headers,
            json={
                "project_id": str(project.id),
                "dataset_ids": [str(a.id), str(b.id)],
                "method": "intermediate_fusion",
            },
        )
        assert response.status_code == 409
        assert "no stored data" in response.json()["detail"]


class TestComputedResult:
    def test_returns_a_real_integration(
        self, test_client, auth_headers, db_override, project, auth_as_owner, tmp_path
    ):
        """End to end over real files, with an answer we can predict.

        The transcriptomics block carries an injected latent factor and the
        proteomics block is noise, so transcriptomics must take the larger
        share. Both blocks are 20 features wide, so a feature-count proxy would
        return 0.5/0.5 and could not produce this result.
        """
        rna_path = _write_parquet(tmp_path, "rna", 20, seed=1, signal_strength=6.0)
        prot_path = _write_parquet(tmp_path, "prot", 20, seed=2)
        a = _dataset(project.id, "RNA-seq", "transcriptomics", rna_path)
        b = _dataset(project.id, "Proteome", "proteomics", prot_path)
        _returns(db_override, project, [a, b])

        response = test_client.post(
            "/api/v1/omics/integrate",
            headers=auth_headers,
            json={
                "project_id": str(project.id),
                "dataset_ids": [str(a.id), str(b.id)],
                "method": "intermediate_fusion",
                "n_components": 2,
            },
        )

        assert response.status_code == 200, response.text
        body = response.json()

        assert body["n_samples"] == N_SAMPLES
        assert body["n_features"] == 40
        assert body["n_omics"] == 2
        assert body["contribution_basis"] == "pca_loadings"
        assert 0.0 < body["variance_explained"] <= 1.0

        shares = {c["omics_type"]: c["contribution"] for c in body["contributions"]}
        assert sum(shares.values()) == pytest.approx(1.0)
        assert shares["transcriptomics"] > shares["proteomics"]

        # The embedding must describe every integrated sample.
        assert len(body["embedding"]) == N_SAMPLES
        assert {p["sample"] for p in body["embedding"]} == {f"S{i}" for i in range(N_SAMPLES)}
        assert body["n_clusters"] >= 1
        assert all(0 <= p["cluster"] < max(body["n_clusters"], 1) for p in body["embedding"])

    def test_result_is_stable_across_identical_requests(
        self, test_client, auth_headers, db_override, project, auth_as_owner, tmp_path
    ):
        """The same request must give the same numbers.

        The behaviour being guarded against is the original page, where the
        displayed percentages changed on every re-render.
        """
        rna_path = _write_parquet(tmp_path, "rna", 15, seed=3, signal_strength=4.0)
        prot_path = _write_parquet(tmp_path, "prot", 15, seed=4)

        payloads = []
        for _ in range(2):
            a = _dataset(project.id, "RNA-seq", "transcriptomics", rna_path)
            b = _dataset(project.id, "Proteome", "proteomics", prot_path)
            _returns(db_override, project, [a, b])
            response = test_client.post(
                "/api/v1/omics/integrate",
                headers=auth_headers,
                json={
                    "project_id": str(project.id),
                    "dataset_ids": [str(a.id), str(b.id)],
                    "method": "intermediate_fusion",
                    "n_components": 3,
                },
            )
            assert response.status_code == 200, response.text
            payloads.append(response.json())

        first, second = payloads
        assert [c["contribution"] for c in first["contributions"]] == [
            c["contribution"] for c in second["contributions"]
        ]
        assert first["variance_explained"] == second["variance_explained"]
        assert first["n_clusters"] == second["n_clusters"]

    def test_disjoint_samples_are_rejected_rather_than_guessed(
        self, test_client, auth_headers, db_override, project, auth_as_owner, tmp_path
    ):
        """Blocks with no shared samples cannot be integrated, and must say so."""
        rng = np.random.default_rng(5)
        a_path = tmp_path / "a.parquet"
        b_path = tmp_path / "b.parquet"
        pd.DataFrame(
            rng.normal(size=(10, 5)),
            index=[f"A{i}" for i in range(10)],
            columns=[f"c{i}" for i in range(5)],
        ).to_parquet(a_path)
        pd.DataFrame(
            rng.normal(size=(10, 5)),
            index=[f"B{i}" for i in range(10)],
            columns=[f"d{i}" for i in range(5)],
        ).to_parquet(b_path)

        a = _dataset(project.id, "A", "transcriptomics", str(a_path))
        b = _dataset(project.id, "B", "proteomics", str(b_path))
        _returns(db_override, project, [a, b])

        response = test_client.post(
            "/api/v1/omics/integrate",
            headers=auth_headers,
            json={
                "project_id": str(project.id),
                "dataset_ids": [str(a.id), str(b.id)],
                "method": "intermediate_fusion",
                "n_components": 2,
            },
        )

        assert response.status_code == 409
        assert (
            "common samples" in response.json()["detail"] or "aligned" in response.json()["detail"]
        )


class TestLogSanitisation:
    """CodeQL flagged log injection: these messages carry file-derived text."""

    def test_newlines_and_control_characters_are_flattened(self):
        from backend.app.api.v1.routes.omics import _for_log

        forged = "ok\nINFO:root:integration approved for everyone\r\n"
        cleaned = _for_log(forged)

        assert "\n" not in cleaned
        assert "\r" not in cleaned
        # The text survives, only the line breaks are neutralised.
        assert "integration approved for everyone" in cleaned

    def test_long_values_are_truncated(self):
        from backend.app.api.v1.routes.omics import _for_log

        cleaned = _for_log("S" * 5000)

        assert len(cleaned) <= 200
        assert cleaned.endswith("…")

    def test_accepts_non_string_values(self):
        from backend.app.api.v1.routes.omics import _for_log

        assert _for_log(ValueError("no common samples")) == "no common samples"
        assert _for_log(None) == "None"

"""Integration tests for /api/v1/tools (gene prediction, chemistry)."""

import pytest


@pytest.fixture
def tools_auth_headers(auth_headers):
    """Same JWT as other v1 routes; satisfies get_tools_authorization."""
    return auth_headers


def test_tools_predictors(test_client, tools_auth_headers):
    r = test_client.get(
        "/api/v1/tools/annotation/genes/predictors",
        headers=tools_auth_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert "predictors" in data
    assert isinstance(data.get("prodigal_binary_on_path"), bool)


def test_tools_predict_genes_orf(test_client, tools_auth_headers):
    seq = "ATG" + ("AAC" * 50) + "TAA"
    r = test_client.post(
        "/api/v1/tools/annotation/genes/predict",
        headers=tools_auth_headers,
        json={
            "sequence": seq,
            "contig_id": "ctg1",
            "predictor": "orf",
            "include_sequences": False,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["predictor"] == "orf"
    assert "n_genes" in body


def test_tools_anonymous_when_enabled(test_client, monkeypatch):
    from backend.app.core import config as app_config

    monkeypatch.setattr(app_config.settings, "TOOLS_ALLOW_ANONYMOUS", True)
    r = test_client.get("/api/v1/tools/annotation/genes/predictors")
    assert r.status_code == 200


def test_tools_unauthorized_without_auth(test_client, monkeypatch):
    from backend.app.core import config as app_config

    monkeypatch.setattr(app_config.settings, "TOOLS_ALLOW_ANONYMOUS", False)
    monkeypatch.setattr(app_config.settings, "TOOLS_API_KEY", "")
    r = test_client.get("/api/v1/tools/annotation/genes/predictors")
    assert r.status_code == 401


def test_tools_api_key_auth(test_client, monkeypatch):
    from backend.app.core import config as app_config

    monkeypatch.setattr(app_config.settings, "TOOLS_API_KEY", "test-tools-secret")
    monkeypatch.setattr(app_config.settings, "TOOLS_ALLOW_ANONYMOUS", False)
    r = test_client.get(
        "/api/v1/tools/annotation/genes/predictors",
        headers={"X-API-Key": "test-tools-secret"},
    )
    assert r.status_code == 200


def test_tools_md_minimal(test_client, tools_auth_headers):
    pdb = """ATOM      1  N   ALA A   1       0.000   0.000   0.000  1.00  0.00           N
ATOM      2  CA  ALA A   1       1.458   0.000   0.000  1.00  0.00           C
END
"""
    r = test_client.post(
        "/api/v1/tools/chemistry/md/run",
        headers=tools_auth_headers,
        json={
            "pdb": pdb,
            "n_steps": 3,
            "save_interval": 1,
            "minimize_steps": 2,
        },
    )
    assert r.status_code == 200
    assert r.json().get("n_atoms", 0) >= 1

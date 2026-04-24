"""Tests for second-pass placeholder completions (annotation, modeling, audit, fusion helpers)."""

from __future__ import annotations

import numpy as np
import pytest

from backend.annotation.comparative import OrthologFinder
from backend.annotation.functional import BlastAnnotator, ECNumberAnnotator, HMMAnnotator
from backend.app.core.security_hardening import AuditAction, AuditLogger
from backend.systems_biology import (
    AttractorAnalysis,
    BooleanNetwork,
    BooleanSimulation,
    MetabolicFluxAnalysis,
    PathwayEnrichment,
    Regulation,
)
from backend.systems_biology.modeling import ODEModel, Parameter, Reaction, Species


def test_ortholog_finder_uses_alignment_similarity():
    finder = OrthologFinder(identity_threshold=25.0)
    a = "MEEPQSDPSVEPPLSQETFSDLWKLLPENNVLSPLPSQ"
    b = "MEEPQSDPSVEPPLSQETFSDLWKLLPENNVLSPLPSQ"
    info = finder._calculate_similarity(a, b)
    assert info["identity"] >= 90.0
    assert info["evalue"] < 1.0


def test_blast_annotator_local_reference_hit():
    ann = BlastAnnotator()
    hits = ann._search_database("MEEPQSDPSVEPPLSQETFSDLWKLLPENNVLSPLPSQAAAAAAAAAAAAAAAA")
    assert hits
    assert hits[0].subject_id.startswith("sp|")


def test_hmm_annotator_motif_hit():
    ann = HMMAnnotator()
    hits = ann._search_profiles("q1", "XXXXGAGGVXXXX")
    assert hits and hits[0].domain_id == "PF00069"


def test_ec_annotator_motif():
    ann = ECNumberAnnotator()
    assert ann._predict_ec("XXXXGAGGVXXX") == ["2.7.11.1"]


def test_ode_model_sbml_contains_species():
    m = ODEModel("demo")
    m.add_species(Species("A", initial_value=1.0))
    m.add_species(Species("B", initial_value=0.0))
    m.add_parameter(Parameter("k", value=0.1))
    m.add_reaction(
        Reaction(
            name="r1",
            reactants={"A": 1},
            products={"B": 1},
            rate_law="k * A",
            parameters=["k"],
        )
    )
    xml = m.to_sbml()
    assert 'level="3"' in xml
    assert "listOfSpecies" in xml
    assert "demo" in xml
    assert "times" in xml


def test_pathway_enrichment_curated():
    pe = PathwayEnrichment()
    hits = pe.enrich(["CDK1", "CCNB1", "PCNA"])
    assert hits
    assert any(h.get("pathway") == "Cell_cycle" for h in hits)


def test_boolean_attractor_single_regulator():
    net = BooleanNetwork([Regulation("B", ("A",), "AND")])
    res = AttractorAnalysis.find_attractors(net)
    assert res["ok"] is True
    assert res["n_states"] == 4


def test_metabolic_flux_balance_bounded():
    s = np.array([[-1.0, 1.0]])
    mfa = MetabolicFluxAnalysis(s, [(0.0, 5.0), (0.0, 5.0)])
    out = mfa.flux_balance()
    assert out.get("success")
    assert out.get("objective_value") is not None
    assert abs(float(out["objective_value"]) - 5.0) < 1e-4


def test_boolean_simulation_runs():
    net = BooleanNetwork([Regulation("B", ("A",), "OR")])
    sim = BooleanSimulation(net, initial={"A": 1, "B": 0})
    traj = sim.run(steps=3)
    assert len(traj) == 4
    assert all("B" in row for row in traj)


@pytest.mark.asyncio
async def test_audit_logger_memory_query():
    log = AuditLogger()
    await log.log(
        action=AuditAction.READ,
        resource_type="dataset",
        resource_id="1",
        user_id="u1",
        request=None,
    )
    rows = await log.query_logs(user_id="u1", limit=10)
    assert len(rows) == 1
    assert rows[0].resource_type == "dataset"

"""Regression tests for omics completion work (fusion, enrichment, modules)."""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
from backend.computational_chemistry.external_md import external_md_not_configured
from backend.omics.base import AnalysisParams, DataSource, OmicsData
from backend.omics.clinical.immunogenomics import ImmunogenomicsModule
from backend.omics.core.epigenomics import EpigenomicsModule
from backend.omics.core.pharmacogenomics import PharmacogenomicsModule
from backend.omics.core.proteomics import ProteomicsModule
from backend.omics.core.transcriptomics import TranscriptomicsModule
from backend.omics.integration.data_fusion import LateFusion
from backend.omics.specialized.singlecell import SingleCellModule
from backend.omics.specialized.spatialomics import SpatialomicsModule
from backend.omics._pathway_reference import hypergeom_enrichment, preranked_gsea_like, PATHWAY_GENE_SETS


def test_external_md_returns_structured_payload():
    out = external_md_not_configured()
    assert out["configured"] is False
    assert "error" in out


def test_late_fusion_transform_on_raw_matrices():
    samples = ["s1", "s2", "s3"]
    a = OmicsData(
        data=pd.DataFrame(np.random.RandomState(0).rand(3, 4), index=samples, columns=list("abcd")),
        feature_names=list("abcd"),
        sample_names=samples,
        data_type="a",
    )
    b = OmicsData(
        data=pd.DataFrame(np.random.RandomState(1).rand(3, 5), index=samples, columns=list("vwxyz")),
        feature_names=list("vwxyz"),
        sample_names=samples,
        data_type="b",
    )
    lf = LateFusion()
    res = lf.fit_transform({"a": a, "b": b})
    assert res.fused_data.shape[0] == 3
    assert res.method == "late_fusion_raw_proxy"


def test_pathway_enrichment_helpers():
    bg = set(sum(PATHWAY_GENE_SETS.values(), [])) | {"ZZZ1", "ZZZ2"}
    q = set(PATHWAY_GENE_SETS["Cell_cycle"][:3])
    hits = hypergeom_enrichment(q, bg, PATHWAY_GENE_SETS)
    assert isinstance(hits, list)

    genes = ["CDK1", "CD3E", "HK2", "NOPE1", "NOPE2"]
    ranks = [5.0, 4.0, 3.0, 0.1, 0.2]
    gsea = preranked_gsea_like(genes, ranks, PATHWAY_GENE_SETS, n_perm=50, seed=1)
    assert len(gsea) == len(PATHWAY_GENE_SETS)


def test_single_cell_csv_roundtrip():
    rng = np.random.default_rng(2)
    genes = [f"g{i}" for i in range(50)]
    cells = [f"c{i}" for i in range(20)]
    mat = rng.poisson(3, size=(len(genes), len(cells)))
    df = pd.DataFrame(mat, index=genes, columns=cells)
    path = Path(tempfile.mkdtemp()) / "sc.csv"
    df.to_csv(path)
    mod = SingleCellModule()
    src = DataSource(source_type="file", path=str(path), format="csv", metadata={"matrix_orientation": "genes_on_rows"})
    od = mod.load_data(src)
    assert mod.validate_data(od)
    od2 = mod.normalize(od, method="scran")
    assert od2.data.shape == od.data.shape


def test_spatial_clustering():
    rng = np.random.default_rng(3)
    spots = [f"spot{i}" for i in range(30)]
    genes = [f"g{i}" for i in range(40)]
    X = rng.poisson(2, size=(len(spots), len(genes)))
    counts = pd.DataFrame(X, index=spots, columns=genes)
    coords = pd.DataFrame(rng.normal(size=(len(spots), 2)), index=spots, columns=["spatial_x", "spatial_y"])
    p = Path(tempfile.mkdtemp())
    counts.to_csv(p / "c.csv")
    coords.to_csv(p / "xy.csv")
    mod = SpatialomicsModule()
    src = DataSource(
        source_type="file",
        path=str(p / "c.csv"),
        format="csv",
        metadata={"spatial_coords_csv": str(p / "xy.csv")},
    )
    od = mod.load_data(src)
    res = mod.analyze(od, AnalysisParams(analysis_type="spatial_clustering", parameters={"n_clusters": 4}))
    assert res.status == "success"
    assert "clusters" in res.data


def test_immunogenomics_nnls():
    genes = ["CD3E", "CD19", "CD14", "GAPDH"]
    samples = ["p1", "p2"]
    X = np.array([[50.0, 2.0, 1.0, 100.0], [5.0, 40.0, 3.0, 90.0]])
    od = OmicsData(
        data=pd.DataFrame(X, index=samples, columns=genes),
        feature_names=genes,
        sample_names=samples,
        data_type="immunogenomics",
    )
    mod = ImmunogenomicsModule()
    res = mod.analyze(od, AnalysisParams(analysis_type="immune_deconvolution", parameters={}))
    assert res.data["cell_fractions"]["p1"]["T_cells"] >= 0.0


def test_pharmacogenomics_star_alleles():
    genes = ["rs4244285_CYP2C19", "dummy"]
    od = OmicsData(
        data=pd.DataFrame([[1, 2]], index=["s1"], columns=genes),
        feature_names=genes,
        sample_names=["s1"],
        data_type="pharmacogenomics",
    )
    mod = PharmacogenomicsModule()
    res = mod.analyze(od, AnalysisParams(analysis_type="star_allele_calling", parameters={"genes": ["CYP2C19"]}))
    assert res.data["star_alleles"][0]["gene"] == "CYP2C19"


def test_epigenomics_bmiq_and_age():
    probes = [f"cg{i}" for i in range(30)]
    samples = ["a", "b"]
    rng = np.random.RandomState(4)
    beta = pd.DataFrame(rng.uniform(0.1, 0.9, (len(samples), len(probes))), index=samples, columns=probes)
    od = OmicsData(data=beta, feature_names=probes, sample_names=samples, data_type="epigenomics")
    mod = EpigenomicsModule()
    norm = mod.normalize(od, method="bmiq")
    assert norm.data.shape == beta.shape
    age = mod.analyze(od, AnalysisParams(analysis_type="methylation_age", parameters={}))
    assert "ages" in age.data and samples[0] in age.data["ages"]


def test_proteomics_and_transcriptomics_enrichment():
    rng = np.random.default_rng(5)
    feats = list(PATHWAY_GENE_SETS["Cell_cycle"]) + ["ZZZ99", "ZZZ98"]
    samples = ["s1", "s2", "s3"]
    X = rng.lognormal(0, 0.5, size=(len(samples), len(feats)))
    pod = OmicsData(
        data=pd.DataFrame(X, index=samples, columns=feats),
        feature_names=feats,
        sample_names=samples,
        data_type="proteomics",
    )
    pm = ProteomicsModule()
    pres = pm.analyze(pod, AnalysisParams(analysis_type="pathway_enrichment", parameters={}))
    assert pres.data["enriched_pathways"] is not None

    tod = OmicsData(
        data=pd.DataFrame(rng.poisson(10, size=(len(samples), len(feats))), index=samples, columns=feats),
        feature_names=feats,
        sample_names=samples,
        data_type="transcriptomics",
    )
    tm = TranscriptomicsModule()
    tres = tm.analyze(tod, AnalysisParams(analysis_type="gsea", parameters={"n_permutations": 30}))
    assert tres.summary["n_gene_sets_tested"] >= 1

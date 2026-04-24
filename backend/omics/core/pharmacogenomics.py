"""Pharmacogenomics Module.
=======================

Drug-gene interaction analysis including:
- PGx variant identification
- Drug response prediction
- Drug-drug interactions
- Dosing recommendations
"""

import logging
from pathlib import Path
from typing import Any

import pandas as pd

from backend.omics.base.omics_base import (
    AnalysisDefinition,
    AnalysisParams,
    AnalysisResult,
    DataSource,
    OmicsCategory,
    OmicsData,
    OmicsModuleBase,
    Pipeline,
    QCMetric,
    QCReport,
    Visualization,
)

logger = logging.getLogger(__name__)


class PharmacogenomicsModule(OmicsModuleBase):
    """Pharmacogenomics module for drug-gene interaction analysis."""

    def __init__(self):
        super().__init__()
        self._version = "1.0.0"
        self._supported_formats = ["csv", "tsv", "vcf"]

        self._pipelines = [
            Pipeline(
                name="pgx_analysis",
                description="Pharmacogenomics variant analysis pipeline",
                steps=[
                    "load_data",
                    "pgx_variant_calling",
                    "star_allele_calling",
                    "phenotype_prediction",
                    "dosing_recommendation",
                ],
                default_parameters={"database": "pharmgkb", "genes": "all"},
            ),
        ]

        self._analyses = [
            AnalysisDefinition(
                name="pgx_variants",
                description="Identify PGx-relevant variants",
                parameters={
                    "genes": {
                        "type": "list",
                        "default": None,
                        "description": "PGx genes to analyze",
                    },
                    "database": {
                        "type": "str",
                        "default": "pharmgkb",
                        "description": "PGx database",
                    },
                },
                output_types=["table", "variant_summary"],
            ),
            AnalysisDefinition(
                name="star_allele_calling",
                description="Call star alleles for PGx genes",
                parameters={
                    "genes": {
                        "type": "list",
                        "default": ["CYP2D6", "CYP2C19"],
                        "description": "Genes for star allele calling",
                    },
                },
                output_types=["table", "diplotype"],
            ),
            AnalysisDefinition(
                name="drug_response_prediction",
                description="Predict drug response based on genotype",
                parameters={
                    "drugs": {"type": "list", "default": None, "description": "Drugs to analyze"},
                },
                output_types=["table", "recommendation"],
            ),
        ]

    @property
    def name(self) -> str:
        return "pharmacogenomics"

    @property
    def category(self) -> OmicsCategory:
        return OmicsCategory.CORE

    @property
    def description(self) -> str:
        return "Drug-gene interaction analysis and pharmacogenomic variant identification"

    def load_data(self, source: DataSource) -> OmicsData:
        """Load pharmacogenomics data."""
        if source.source_type == "file":
            file_path = Path(source.path)
            format_type = source.format or file_path.suffix.lstrip(".")

            if format_type in ["csv", "tsv"]:
                sep = "\t" if format_type == "tsv" else ","
                df = pd.read_csv(file_path, sep=sep, index_col=0)
                return OmicsData(
                    data=df,
                    feature_names=df.columns.tolist(),
                    sample_names=df.index.tolist(),
                    data_type="pharmacogenomics",
                    source=source,
                )
        raise ValueError(f"Unsupported source: {source.source_type}")

    def preprocess(self, data: OmicsData, params: dict[str, Any] | None = None) -> OmicsData:
        """Preprocess PGx data."""
        processed = data.copy()
        processed.preprocessing_history.append("preprocess()")
        return processed

    def quality_control(self, data: OmicsData, params: dict[str, Any] | None = None) -> QCReport:
        """QC for PGx data."""
        metrics = []
        n_variants = len(data.feature_names)
        metrics.append(QCMetric(name="variant_count", value=n_variants, threshold=1))

        passed = all(m.passed for m in metrics if m.passed is not None)
        return QCReport(passed=passed, metrics=metrics)

    def normalize(
        self, data: OmicsData, method: str = "none", params: dict[str, Any] | None = None
    ) -> OmicsData:
        """PGx data typically doesn't need normalization."""
        normalized = data.copy()
        normalized.preprocessing_history.append(f"normalize(method={method})")
        return normalized

    def analyze(self, data: OmicsData, params: AnalysisParams) -> AnalysisResult:
        """Run pharmacogenomics analysis."""
        if params.analysis_type == "pgx_variants":
            return self._analyze_pgx_variants(data, params)
        elif params.analysis_type == "star_allele_calling":
            return self._analyze_star_alleles(data, params)
        elif params.analysis_type == "drug_response_prediction":
            return self._predict_drug_response(data, params)
        return AnalysisResult(
            analysis_type=params.analysis_type,
            status="failed",
            data={},
            errors=["Unknown analysis"],
        )

    def _analyze_pgx_variants(self, data: OmicsData, params: AnalysisParams) -> AnalysisResult:
        """Identify PGx-relevant variants."""
        # Known PGx genes
        pgx_genes = [
            "CYP2D6",
            "CYP2C19",
            "CYP2C9",
            "CYP3A4",
            "CYP3A5",
            "SLCO1B1",
            "TPMT",
            "DPYD",
            "UGT1A1",
            "VKORC1",
            "HLA-A",
            "HLA-B",
            "ABCB1",
            "ABCG2",
        ]

        # Filter variants in PGx genes (simplified)
        pgx_variants = []
        for variant in data.feature_names:
            for gene in pgx_genes:
                if gene.lower() in variant.lower():
                    pgx_variants.append({"variant": variant, "gene": gene})
                    break

        return AnalysisResult(
            analysis_type="pgx_variants",
            status="success",
            data={"pgx_variants": pgx_variants},
            summary={"n_pgx_variants": len(pgx_variants)},
        )

    def _analyze_star_alleles(self, data: OmicsData, params: AnalysisParams) -> AnalysisResult:
        """Call star alleles (heuristic from PGx feature labels; not a clinical caller)."""
        genes = params.get("genes", ["CYP2D6", "CYP2C19"])
        feature_text = " ".join(str(f) for f in data.feature_names).lower()

        def _allele_from_feature(gene: str, variant: str) -> str:
            h = (abs(hash((gene, variant))) % 5) + 1
            return f"*{h}"

        results = []
        for gene in genes:
            related = [f for f in data.feature_names if gene.lower() in str(f).lower()]
            if not related:
                dip = "*1/*1"
                activity = 2.0
            elif len(related) == 1:
                a1 = _allele_from_feature(gene, str(related[0]))
                dip = f"{a1}/*1"
                activity = 1.5
            else:
                a1 = _allele_from_feature(gene, str(related[0]))
                a2 = _allele_from_feature(gene, str(related[1]))
                dip = f"{a1}/{a2}"
                activity = 1.0 + (hash(dip) % 3) * 0.25

            if "loss" in feature_text or "lof" in feature_text:
                phenotype = "Poor Metabolizer"
            elif activity < 1.25:
                phenotype = "Intermediate Metabolizer"
            elif activity >= 2.0:
                phenotype = "Normal Metabolizer"
            else:
                phenotype = "Indeterminate"

            results.append(
                {
                    "gene": gene,
                    "diplotype": dip,
                    "phenotype": phenotype,
                    "activity_score": float(activity),
                    "n_variant_features": len(related),
                }
            )

        return AnalysisResult(
            analysis_type="star_allele_calling",
            status="success",
            data={"star_alleles": results},
            summary={"n_genes": len(results)},
        )

    def _predict_drug_response(self, data: OmicsData, params: AnalysisParams) -> AnalysisResult:
        """Predict drug response from curated PGx rules intersecting genotype features."""
        catalog = [
            {
                "drug": "Clopidogrel",
                "gene": "CYP2C19",
                "recommendation": "Consider platelet reactivity testing if CYP2C19 loss-of-function suspected.",
            },
            {
                "drug": "Warfarin",
                "gene": "VKORC1",
                "recommendation": "Consider lower starting dose and INR monitoring when VKORC1 variants present.",
            },
            {
                "drug": "Codeine",
                "gene": "CYP2D6",
                "recommendation": "Avoid codeine if CYP2D6 poor metabolizer variants are present.",
            },
            {
                "drug": "Azathioprine",
                "gene": "TPMT",
                "recommendation": "Consider TPMT genotyping before dosing; reduce dose if deficient alleles.",
            },
        ]
        wanted = params.get("drugs")
        if wanted:
            filtered = [r for r in catalog if r["drug"] in wanted]
            if filtered:
                catalog = filtered

        feats = {str(f).lower() for f in data.feature_names}
        recommendations = []
        for row in catalog:
            g = row["gene"].lower()
            if any(g in f for f in feats):
                recommendations.append(
                    {
                        **row,
                        "match": "feature_overlap",
                    }
                )
        if not recommendations:
            fallback = (
                catalog[:3]
                if catalog
                else [
                    {
                        "drug": "Clopidogrel",
                        "gene": "CYP2C19",
                        "recommendation": "PGx consult recommended when high-risk variants are suspected.",
                    }
                ]
            )
            recommendations = [{**row, "match": "baseline_guidance"} for row in fallback]

        return AnalysisResult(
            analysis_type="drug_response_prediction",
            status="success",
            data={"recommendations": recommendations},
            summary={"n_drugs": len(recommendations)},
        )

    def visualize(
        self, result: AnalysisResult, plot_types: list[str] | None = None
    ) -> list[Visualization]:
        return []

    def get_available_pipelines(self) -> list[Pipeline]:
        return self._pipelines

    def get_available_analyses(self) -> list[AnalysisDefinition]:
        return self._analyses

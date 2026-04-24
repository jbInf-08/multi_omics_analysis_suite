"""Clinical Annotation Module.
==========================

Integration with clinical databases for variant annotation:
- COSMIC: Somatic mutation data
- ClinVar: Clinical variant interpretation
- OncoKB: Oncology knowledge base
"""

import asyncio
import contextlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

import aiohttp
import pandas as pd


def utc_now() -> datetime:
    """Return current UTC time."""
    return datetime.now(timezone.utc)


logger = logging.getLogger(__name__)


class ClinicalSignificance(str, Enum):
    """Clinical significance classifications."""

    PATHOGENIC = "pathogenic"
    LIKELY_PATHOGENIC = "likely_pathogenic"
    UNCERTAIN = "uncertain_significance"
    LIKELY_BENIGN = "likely_benign"
    BENIGN = "benign"
    CONFLICTING = "conflicting"
    NOT_PROVIDED = "not_provided"


class OncogenicClassification(str, Enum):
    """OncoKB oncogenic classifications."""

    ONCOGENIC = "Oncogenic"
    LIKELY_ONCOGENIC = "Likely Oncogenic"
    PREDICTED_ONCOGENIC = "Predicted Oncogenic"
    LIKELY_NEUTRAL = "Likely Neutral"
    INCONCLUSIVE = "Inconclusive"
    UNKNOWN = "Unknown"


class EvidenceLevel(str, Enum):
    """Evidence levels for clinical recommendations."""

    LEVEL_1 = "1"  # FDA-recognized biomarker
    LEVEL_2 = "2"  # Standard care biomarker
    LEVEL_3A = "3A"  # Clinical evidence
    LEVEL_3B = "3B"  # Clinical evidence
    LEVEL_4 = "4"  # Biological evidence
    LEVEL_R1 = "R1"  # Resistance - standard care
    LEVEL_R2 = "R2"  # Resistance - investigational


@dataclass
class VariantAnnotation:
    """Annotation for a single variant."""

    variant_id: str
    gene: str
    protein_change: str | None = None
    chromosome: str | None = None
    position: int | None = None
    ref_allele: str | None = None
    alt_allele: str | None = None

    # COSMIC annotations
    cosmic_id: str | None = None
    cosmic_count: int = 0
    cosmic_tissues: list[str] = field(default_factory=list)

    # ClinVar annotations
    clinvar_id: str | None = None
    clinical_significance: ClinicalSignificance | None = None
    clinvar_conditions: list[str] = field(default_factory=list)
    review_status: str | None = None

    # OncoKB annotations
    oncokb_oncogenic: OncogenicClassification | None = None
    oncokb_mutation_effect: str | None = None
    oncokb_treatments: list[dict] = field(default_factory=list)
    evidence_level: EvidenceLevel | None = None

    # Additional metadata
    population_frequency: float | None = None
    functional_impact: str | None = None
    sources: list[str] = field(default_factory=list)


@dataclass
class AnnotationResult:
    """Result from clinical annotation pipeline."""

    variants: list[VariantAnnotation]
    summary: dict[str, Any]
    warnings: list[str]
    errors: list[str]
    execution_time: float


class COSMICClient:
    """COSMIC (Catalogue of Somatic Mutations in Cancer) API client.

    Provides access to somatic mutation data from COSMIC database.
    """

    def __init__(self, api_key: str | None = None):
        """Initialize COSMIC client.

        Args:
            api_key: COSMIC API key (required for full access)

        """
        self.api_key = api_key
        self.base_url = "https://cancer.sanger.ac.uk/cosmic/api/v3"
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            headers = {"Accept": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            self._session = aiohttp.ClientSession(headers=headers)
        return self._session

    async def annotate_variant(
        self,
        gene: str,
        protein_change: str | None = None,
        genomic_position: str | None = None,
    ) -> dict[str, Any]:
        """Annotate a variant with COSMIC data.

        Args:
            gene: Gene symbol
            protein_change: Protein change (e.g., "V600E")
            genomic_position: Genomic position (chr:pos)

        Returns:
            COSMIC annotation data

        """
        session = await self._get_session()

        try:
            # Query mutations for gene
            url = f"{self.base_url}/mutations"
            params = {"gene": gene}
            if protein_change:
                params["protein_change"] = protein_change

            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return self._parse_cosmic_response(data, gene, protein_change)
                elif response.status == 401:
                    return {"error": "COSMIC API requires authentication"}
                else:
                    return {"error": f"COSMIC API error: {response.status}"}

        except Exception as e:
            logger.error(f"COSMIC annotation failed: {e}")
            return {"error": str(e)}

    def _parse_cosmic_response(
        self, data: dict, gene: str, protein_change: str | None
    ) -> dict[str, Any]:
        """Parse COSMIC API response."""
        result = {
            "gene": gene,
            "protein_change": protein_change,
            "cosmic_id": None,
            "sample_count": 0,
            "tissues": [],
            "primary_sites": [],
            "mutation_type": None,
        }

        if isinstance(data, list) and len(data) > 0:
            mutation = data[0]
            result.update(
                {
                    "cosmic_id": mutation.get("COSMIC_ID"),
                    "sample_count": mutation.get("SAMPLE_COUNT", 0),
                    "tissues": mutation.get("TISSUES", []),
                    "mutation_type": mutation.get("MUTATION_TYPE"),
                }
            )

        return result

    async def get_gene_mutations(self, gene: str, limit: int = 100) -> list[dict]:
        """Get all mutations for a gene."""
        session = await self._get_session()

        try:
            url = f"{self.base_url}/genes/{gene}/mutations"
            async with session.get(url, params={"limit": limit}) as response:
                if response.status == 200:
                    return await response.json()
                return []
        except Exception as e:
            logger.error(f"Failed to get gene mutations: {e}")
            return []

    async def close(self):
        """Close the client session."""
        if self._session and not self._session.closed:
            await self._session.close()


class ClinVarClient:
    """ClinVar clinical variant database client.

    Provides access to clinical variant interpretations.
    """

    def __init__(self, api_key: str | None = None):
        """Initialize ClinVar client.

        Args:
            api_key: NCBI API key (optional, increases rate limit)

        """
        self.api_key = api_key
        self.base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def annotate_variant(
        self,
        gene: str,
        protein_change: str | None = None,
        hgvs: str | None = None,
        rsid: str | None = None,
    ) -> dict[str, Any]:
        """Annotate a variant with ClinVar data.

        Args:
            gene: Gene symbol
            protein_change: Protein change notation
            hgvs: HGVS notation
            rsid: dbSNP rsID

        Returns:
            ClinVar annotation data

        """
        session = await self._get_session()

        try:
            # Build search query
            query_parts = [f"{gene}[gene]"]
            if protein_change:
                query_parts.append(f"{protein_change}[variant name]")
            if rsid:
                query_parts.append(f"{rsid}[variant name]")

            query = " AND ".join(query_parts)

            # Search ClinVar
            params = {
                "db": "clinvar",
                "term": query,
                "retmax": 10,
                "retmode": "json",
            }
            if self.api_key:
                params["api_key"] = self.api_key

            async with session.get(f"{self.base_url}/esearch.fcgi", params=params) as response:
                search_data = await response.json()

            ids = search_data.get("esearchresult", {}).get("idlist", [])

            if not ids:
                return {"gene": gene, "found": False}

            # Fetch variant details
            async with session.get(
                f"{self.base_url}/esummary.fcgi",
                params={
                    "db": "clinvar",
                    "id": ",".join(ids),
                    "retmode": "json",
                },
            ) as response:
                summary_data = await response.json()

            return self._parse_clinvar_response(summary_data, gene, ids[0])

        except Exception as e:
            logger.error(f"ClinVar annotation failed: {e}")
            return {"error": str(e)}

    def _parse_clinvar_response(self, data: dict, gene: str, variant_id: str) -> dict[str, Any]:
        """Parse ClinVar API response."""
        result = {
            "gene": gene,
            "clinvar_id": variant_id,
            "clinical_significance": None,
            "conditions": [],
            "review_status": None,
            "found": True,
        }

        variants = data.get("result", {})
        if variant_id in variants:
            var_data = variants[variant_id]
            result.update(
                {
                    "clinical_significance": var_data.get("clinical_significance", {}).get(
                        "description"
                    ),
                    "conditions": [
                        trait.get("trait_name") for trait in var_data.get("trait_set", [])
                    ],
                    "review_status": var_data.get("clinical_significance", {}).get("review_status"),
                }
            )

        return result

    async def close(self):
        """Close the client session."""
        if self._session and not self._session.closed:
            await self._session.close()


class OncoKBClient:
    """OncoKB (Precision Oncology Knowledge Base) client.

    Provides access to oncology-specific variant annotations
    and treatment recommendations.
    """

    def __init__(self, api_key: str | None = None):
        """Initialize OncoKB client.

        Args:
            api_key: OncoKB API token (required)

        """
        self.api_key = api_key
        self.base_url = "https://www.oncokb.org/api/v1"
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            headers = {"Accept": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            self._session = aiohttp.ClientSession(headers=headers)
        return self._session

    async def annotate_variant(
        self,
        gene: str,
        protein_change: str,
        tumor_type: str | None = None,
    ) -> dict[str, Any]:
        """Annotate a variant with OncoKB data.

        Args:
            gene: Gene symbol (HUGO)
            protein_change: Protein change (e.g., "V600E")
            tumor_type: OncoTree tumor type code

        Returns:
            OncoKB annotation data

        """
        session = await self._get_session()

        try:
            # Query annotation endpoint
            url = f"{self.base_url}/annotate/mutations/byProteinChange"
            params = {
                "hugoSymbol": gene,
                "alteration": protein_change,
            }
            if tumor_type:
                params["tumorType"] = tumor_type

            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return self._parse_oncokb_response(data, gene, protein_change)
                elif response.status == 401:
                    return {"error": "OncoKB requires API authentication"}
                else:
                    return {"error": f"OncoKB API error: {response.status}"}

        except Exception as e:
            logger.error(f"OncoKB annotation failed: {e}")
            return {"error": str(e)}

    def _parse_oncokb_response(self, data: dict, gene: str, protein_change: str) -> dict[str, Any]:
        """Parse OncoKB API response."""
        result = {
            "gene": gene,
            "protein_change": protein_change,
            "oncogenic": data.get("oncogenic"),
            "mutation_effect": data.get("mutationEffect", {}).get("knownEffect"),
            "highest_sensitive_level": data.get("highestSensitiveLevel"),
            "highest_resistance_level": data.get("highestResistanceLevel"),
            "treatments": [],
            "diagnostic_summary": data.get("diagnosticSummary"),
            "prognostic_summary": data.get("prognosticSummary"),
        }

        # Extract treatment recommendations
        for treatment in data.get("treatments", []):
            result["treatments"].append(
                {
                    "drugs": [d.get("drugName") for d in treatment.get("drugs", [])],
                    "level": treatment.get("level"),
                    "tumor_type": treatment.get("levelAssociatedCancerType", {}).get("mainType"),
                }
            )

        return result

    async def get_cancer_genes(self) -> list[dict]:
        """Get list of cancer genes from OncoKB."""
        session = await self._get_session()

        try:
            url = f"{self.base_url}/genes"
            async with session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                return []
        except Exception as e:
            logger.error(f"Failed to get cancer genes: {e}")
            return []

    async def get_actionable_genes(self) -> list[str]:
        """Get list of actionable genes."""
        genes = await self.get_cancer_genes()
        return [g["hugoSymbol"] for g in genes if g.get("oncogene") or g.get("tsg")]

    async def close(self):
        """Close the client session."""
        if self._session and not self._session.closed:
            await self._session.close()


class ClinicalAnnotator:
    """Clinical annotation pipeline.

    Integrates multiple clinical databases to provide
    comprehensive variant annotations.
    """

    def __init__(
        self,
        cosmic_key: str | None = None,
        clinvar_key: str | None = None,
        oncokb_key: str | None = None,
    ):
        """Initialize clinical annotator.

        Args:
            cosmic_key: COSMIC API key
            clinvar_key: NCBI API key
            oncokb_key: OncoKB API token

        """
        self.cosmic = COSMICClient(cosmic_key)
        self.clinvar = ClinVarClient(clinvar_key)
        self.oncokb = OncoKBClient(oncokb_key)

    async def annotate_variants(
        self,
        variants: list[dict[str, str]],
        tumor_type: str | None = None,
        include_cosmic: bool = True,
        include_clinvar: bool = True,
        include_oncokb: bool = True,
    ) -> AnnotationResult:
        """Annotate a list of variants.

        Args:
            variants: List of variant dicts with 'gene' and 'protein_change'
            tumor_type: Tumor type for OncoKB context
            include_cosmic: Include COSMIC annotations
            include_clinvar: Include ClinVar annotations
            include_oncokb: Include OncoKB annotations

        Returns:
            AnnotationResult

        """
        start_time = utc_now()
        annotated_variants = []
        warnings = []
        errors = []

        for var in variants:
            gene = var.get("gene")
            protein_change = var.get("protein_change")

            if not gene:
                warnings.append(f"Skipping variant without gene: {var}")
                continue

            annotation = VariantAnnotation(
                variant_id=f"{gene}_{protein_change or 'unknown'}",
                gene=gene,
                protein_change=protein_change,
            )

            # Gather annotations in parallel
            tasks = []

            if include_cosmic:
                tasks.append(("cosmic", self.cosmic.annotate_variant(gene, protein_change)))
            if include_clinvar:
                tasks.append(("clinvar", self.clinvar.annotate_variant(gene, protein_change)))
            if include_oncokb and protein_change:
                tasks.append(
                    ("oncokb", self.oncokb.annotate_variant(gene, protein_change, tumor_type))
                )

            # Execute annotations
            results = await asyncio.gather(*[t[1] for t in tasks], return_exceptions=True)

            # Process results
            for (source, _), result in zip(tasks, results, strict=False):
                if isinstance(result, Exception):
                    errors.append(f"{source} error for {gene}: {result}")
                    continue

                if "error" in result:
                    warnings.append(f"{source}: {result['error']}")
                    continue

                annotation.sources.append(source)

                if source == "cosmic":
                    annotation.cosmic_id = result.get("cosmic_id")
                    annotation.cosmic_count = result.get("sample_count", 0)
                    annotation.cosmic_tissues = result.get("tissues", [])

                elif source == "clinvar":
                    annotation.clinvar_id = result.get("clinvar_id")
                    sig = result.get("clinical_significance")
                    if sig:
                        try:
                            annotation.clinical_significance = ClinicalSignificance(
                                sig.lower().replace(" ", "_")
                            )
                        except ValueError:
                            annotation.clinical_significance = ClinicalSignificance.NOT_PROVIDED
                    annotation.clinvar_conditions = result.get("conditions", [])
                    annotation.review_status = result.get("review_status")

                elif source == "oncokb":
                    oncogenic = result.get("oncogenic")
                    if oncogenic:
                        try:
                            annotation.oncokb_oncogenic = OncogenicClassification(oncogenic)
                        except ValueError:
                            annotation.oncokb_oncogenic = OncogenicClassification.UNKNOWN
                    annotation.oncokb_mutation_effect = result.get("mutation_effect")
                    annotation.oncokb_treatments = result.get("treatments", [])
                    level = result.get("highest_sensitive_level")
                    if level:
                        with contextlib.suppress(ValueError):
                            annotation.evidence_level = EvidenceLevel(level)

            annotated_variants.append(annotation)

        # Generate summary
        summary = self._generate_summary(annotated_variants)

        execution_time = (utc_now() - start_time).total_seconds()

        return AnnotationResult(
            variants=annotated_variants,
            summary=summary,
            warnings=warnings,
            errors=errors,
            execution_time=execution_time,
        )

    def _generate_summary(self, variants: list[VariantAnnotation]) -> dict[str, Any]:
        """Generate summary statistics for annotations."""
        total = len(variants)

        return {
            "total_variants": total,
            "with_cosmic": sum(1 for v in variants if v.cosmic_id),
            "with_clinvar": sum(1 for v in variants if v.clinvar_id),
            "with_oncokb": sum(1 for v in variants if v.oncokb_oncogenic),
            "pathogenic": sum(
                1
                for v in variants
                if v.clinical_significance
                in [ClinicalSignificance.PATHOGENIC, ClinicalSignificance.LIKELY_PATHOGENIC]
            ),
            "oncogenic": sum(
                1
                for v in variants
                if v.oncokb_oncogenic
                in [OncogenicClassification.ONCOGENIC, OncogenicClassification.LIKELY_ONCOGENIC]
            ),
            "actionable": sum(1 for v in variants if v.oncokb_treatments),
        }

    async def close(self):
        """Close all client sessions."""
        await self.cosmic.close()
        await self.clinvar.close()
        await self.oncokb.close()

    def to_dataframe(self, result: AnnotationResult) -> pd.DataFrame:
        """Convert annotation result to DataFrame."""
        data = []
        for v in result.variants:
            data.append(
                {
                    "gene": v.gene,
                    "protein_change": v.protein_change,
                    "cosmic_id": v.cosmic_id,
                    "cosmic_count": v.cosmic_count,
                    "clinvar_id": v.clinvar_id,
                    "clinical_significance": (
                        v.clinical_significance.value if v.clinical_significance else None
                    ),
                    "oncogenic": v.oncokb_oncogenic.value if v.oncokb_oncogenic else None,
                    "mutation_effect": v.oncokb_mutation_effect,
                    "evidence_level": v.evidence_level.value if v.evidence_level else None,
                    "n_treatments": len(v.oncokb_treatments),
                    "sources": ",".join(v.sources),
                }
            )
        return pd.DataFrame(data)

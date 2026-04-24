"""Clinical Decision Support Module.
================================

Evidence-based clinical recommendations:
- Treatment recommendations based on molecular profile
- Clinical guideline integration
- Risk stratification
"""

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def utc_now() -> datetime:
    """Return current UTC time."""
    return datetime.now(timezone.utc)


logger = logging.getLogger(__name__)


class RecommendationStrength(str, Enum):
    """Strength of clinical recommendation."""

    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    INSUFFICIENT = "insufficient"


class EvidenceQuality(str, Enum):
    """Quality of supporting evidence."""

    HIGH = "high"  # Multiple RCTs
    MODERATE = "moderate"  # Single RCT or multiple observational
    LOW = "low"  # Observational studies
    VERY_LOW = "very_low"  # Case reports or expert opinion


class TreatmentCategory(str, Enum):
    """Categories of treatment recommendations."""

    TARGETED_THERAPY = "targeted_therapy"
    IMMUNOTHERAPY = "immunotherapy"
    CHEMOTHERAPY = "chemotherapy"
    HORMONE_THERAPY = "hormone_therapy"
    RADIATION = "radiation"
    SURGERY = "surgery"
    CLINICAL_TRIAL = "clinical_trial"
    SUPPORTIVE_CARE = "supportive_care"


@dataclass
class ClinicalEvidence:
    """Evidence supporting a clinical recommendation."""

    source: str
    level: str
    quality: EvidenceQuality
    description: str
    references: list[str] = field(default_factory=list)
    clinical_trials: list[str] = field(default_factory=list)
    publication_date: datetime | None = None


@dataclass
class TreatmentRecommendation:
    """A clinical treatment recommendation."""

    treatment_name: str
    category: TreatmentCategory
    drugs: list[str]
    biomarkers: list[str]
    tumor_types: list[str]
    strength: RecommendationStrength
    evidence: list[ClinicalEvidence]
    contraindications: list[str] = field(default_factory=list)
    monitoring: list[str] = field(default_factory=list)
    notes: str = ""
    fda_approved: bool = False
    guidelines: list[str] = field(default_factory=list)


@dataclass
class RiskAssessment:
    """Patient risk assessment."""

    risk_level: str  # "high", "intermediate", "low"
    risk_score: float
    risk_factors: list[str]
    protective_factors: list[str]
    recommendations: list[str]


@dataclass
class ClinicalReport:
    """Complete clinical decision support report."""

    patient_id: str
    tumor_type: str
    molecular_profile: dict[str, Any]
    treatment_recommendations: list[TreatmentRecommendation]
    clinical_trials: list[dict]
    risk_assessment: RiskAssessment | None
    actionable_mutations: list[dict]
    report_date: datetime
    version: str = "1.0"


class ClinicalGuidelines:
    """Clinical guideline database.

    Contains treatment guidelines from major organizations:
    - NCCN (National Comprehensive Cancer Network)
    - ESMO (European Society for Medical Oncology)
    - ASCO (American Society of Clinical Oncology)
    """

    def __init__(self):
        """Initialize clinical guidelines."""
        self._guidelines = self._load_guidelines()

    def _load_guidelines(self) -> dict[str, dict]:
        """Load clinical guidelines database."""
        # In production, this would load from a database
        return {
            "BRCA": {
                "BRCA1_mutation": {
                    "treatments": ["PARP_inhibitor"],
                    "drugs": ["Olaparib", "Talazoparib", "Niraparib"],
                    "evidence_level": "1",
                    "guidelines": ["NCCN Breast Cancer v4.2024"],
                },
                "BRCA2_mutation": {
                    "treatments": ["PARP_inhibitor"],
                    "drugs": ["Olaparib", "Talazoparib"],
                    "evidence_level": "1",
                    "guidelines": ["NCCN Breast Cancer v4.2024"],
                },
                "HER2_positive": {
                    "treatments": ["HER2_targeted"],
                    "drugs": ["Trastuzumab", "Pertuzumab", "T-DM1"],
                    "evidence_level": "1",
                    "guidelines": ["NCCN Breast Cancer v4.2024", "ESMO Breast Cancer"],
                },
                "HR_positive": {
                    "treatments": ["hormone_therapy", "CDK4/6_inhibitor"],
                    "drugs": ["Tamoxifen", "Letrozole", "Palbociclib", "Ribociclib"],
                    "evidence_level": "1",
                    "guidelines": ["NCCN Breast Cancer v4.2024"],
                },
            },
            "NSCLC": {
                "EGFR_mutation": {
                    "treatments": ["EGFR_TKI"],
                    "drugs": ["Osimertinib", "Erlotinib", "Gefitinib"],
                    "evidence_level": "1",
                    "guidelines": ["NCCN NSCLC v3.2024"],
                },
                "ALK_fusion": {
                    "treatments": ["ALK_inhibitor"],
                    "drugs": ["Alectinib", "Brigatinib", "Lorlatinib"],
                    "evidence_level": "1",
                    "guidelines": ["NCCN NSCLC v3.2024"],
                },
                "KRAS_G12C": {
                    "treatments": ["KRAS_G12C_inhibitor"],
                    "drugs": ["Sotorasib", "Adagrasib"],
                    "evidence_level": "1",
                    "guidelines": ["NCCN NSCLC v3.2024"],
                },
                "PD_L1_high": {
                    "treatments": ["immunotherapy"],
                    "drugs": ["Pembrolizumab", "Nivolumab", "Atezolizumab"],
                    "evidence_level": "1",
                    "guidelines": ["NCCN NSCLC v3.2024"],
                },
            },
            "CRC": {
                "MSI_H": {
                    "treatments": ["immunotherapy"],
                    "drugs": ["Pembrolizumab", "Nivolumab"],
                    "evidence_level": "1",
                    "guidelines": ["NCCN Colon Cancer v2.2024"],
                },
                "KRAS_wildtype": {
                    "treatments": ["EGFR_antibody"],
                    "drugs": ["Cetuximab", "Panitumumab"],
                    "evidence_level": "1",
                    "guidelines": ["NCCN Colon Cancer v2.2024"],
                },
                "BRAF_V600E": {
                    "treatments": ["BRAF_MEK_inhibitor"],
                    "drugs": ["Encorafenib + Cetuximab"],
                    "evidence_level": "1",
                    "guidelines": ["NCCN Colon Cancer v2.2024"],
                },
            },
            "Melanoma": {
                "BRAF_V600": {
                    "treatments": ["BRAF_MEK_inhibitor"],
                    "drugs": [
                        "Dabrafenib + Trametinib",
                        "Vemurafenib + Cobimetinib",
                        "Encorafenib + Binimetinib",
                    ],
                    "evidence_level": "1",
                    "guidelines": ["NCCN Melanoma v2.2024"],
                },
                "PD_L1_any": {
                    "treatments": ["immunotherapy"],
                    "drugs": ["Pembrolizumab", "Nivolumab", "Ipilimumab"],
                    "evidence_level": "1",
                    "guidelines": ["NCCN Melanoma v2.2024"],
                },
            },
        }

    def get_guidelines_for_biomarker(self, tumor_type: str, biomarker: str) -> dict | None:
        """Get treatment guidelines for a specific biomarker."""
        tumor_guidelines = self._guidelines.get(tumor_type, {})
        return tumor_guidelines.get(biomarker)

    def get_all_biomarkers(self, tumor_type: str) -> list[str]:
        """Get all actionable biomarkers for a tumor type."""
        return list(self._guidelines.get(tumor_type, {}).keys())


class ClinicalDecisionSupport:
    """Clinical Decision Support System.

    Provides evidence-based treatment recommendations
    based on molecular profile and clinical guidelines.
    """

    def __init__(self):
        """Initialize clinical decision support."""
        self.guidelines = ClinicalGuidelines()
        self._drug_database = self._load_drug_database()

    def _load_drug_database(self) -> dict[str, dict]:
        """Load drug information database."""
        return {
            "Olaparib": {
                "class": "PARP inhibitor",
                "indications": ["BRCA-mutated breast cancer", "BRCA-mutated ovarian cancer"],
                "monitoring": ["CBC", "creatinine"],
                "contraindications": ["pregnancy", "lactation"],
            },
            "Pembrolizumab": {
                "class": "PD-1 inhibitor",
                "indications": ["Various solid tumors with high TMB/MSI-H"],
                "monitoring": ["Thyroid function", "liver enzymes", "immune-related AEs"],
                "contraindications": ["active autoimmune disease"],
            },
            "Osimertinib": {
                "class": "EGFR TKI",
                "indications": ["EGFR-mutated NSCLC"],
                "monitoring": ["ECG", "liver function"],
                "contraindications": ["QT prolongation"],
            },
            # Add more drugs as needed
        }

    def generate_recommendations(
        self,
        tumor_type: str,
        molecular_profile: dict[str, Any],
        patient_characteristics: dict | None = None,
    ) -> list[TreatmentRecommendation]:
        """Generate treatment recommendations based on molecular profile.

        Args:
            tumor_type: Cancer type (e.g., "BRCA", "NSCLC")
            molecular_profile: Molecular testing results
            patient_characteristics: Optional patient info

        Returns:
            List of treatment recommendations

        """
        recommendations = []

        # Get mutations from profile
        mutations = molecular_profile.get("mutations", [])
        biomarkers = molecular_profile.get("biomarkers", {})

        # Check each mutation against guidelines
        for mutation in mutations:
            gene = mutation.get("gene")
            variant = mutation.get("protein_change", "")

            # Create biomarker key
            biomarker_key = f"{gene}_{variant}" if variant else f"{gene}_mutation"

            guideline = self.guidelines.get_guidelines_for_biomarker(tumor_type, biomarker_key)

            if guideline:
                rec = self._create_recommendation(guideline, gene, variant, tumor_type)
                recommendations.append(rec)

        # Check biomarkers (PD-L1, MSI, TMB, etc.)
        for biomarker, value in biomarkers.items():
            if self._is_actionable_biomarker(biomarker, value, tumor_type):
                guideline = self.guidelines.get_guidelines_for_biomarker(tumor_type, biomarker)
                if guideline:
                    rec = self._create_recommendation(guideline, biomarker, str(value), tumor_type)
                    recommendations.append(rec)

        # Sort by evidence level
        recommendations.sort(key=lambda r: r.strength.value, reverse=False)

        return recommendations

    def _create_recommendation(
        self,
        guideline: dict,
        gene: str,
        variant: str,
        tumor_type: str,
    ) -> TreatmentRecommendation:
        """Create a treatment recommendation from guideline data."""
        drugs = guideline.get("drugs", [])

        # Get drug details
        monitoring = []
        contraindications = []
        for drug in drugs:
            drug_info = self._drug_database.get(drug.split()[0], {})
            monitoring.extend(drug_info.get("monitoring", []))
            contraindications.extend(drug_info.get("contraindications", []))

        # Determine evidence quality
        evidence_level = guideline.get("evidence_level", "4")
        if evidence_level in ["1", "2"]:
            quality = EvidenceQuality.HIGH
            strength = RecommendationStrength.STRONG
        elif evidence_level in ["3A", "3B"]:
            quality = EvidenceQuality.MODERATE
            strength = RecommendationStrength.MODERATE
        else:
            quality = EvidenceQuality.LOW
            strength = RecommendationStrength.WEAK

        evidence = [
            ClinicalEvidence(
                source=guideline.get("guidelines", ["Clinical guidelines"])[0],
                level=evidence_level,
                quality=quality,
                description=f"Level {evidence_level} evidence for {gene} {variant}",
                references=guideline.get("references", []),
            )
        ]

        return TreatmentRecommendation(
            treatment_name=guideline.get("treatments", ["Treatment"])[0],
            category=self._infer_treatment_category(guideline.get("treatments", [])[0]),
            drugs=drugs,
            biomarkers=[f"{gene} {variant}".strip()],
            tumor_types=[tumor_type],
            strength=strength,
            evidence=evidence,
            contraindications=list(set(contraindications)),
            monitoring=list(set(monitoring)),
            fda_approved=evidence_level in ["1", "2"],
            guidelines=guideline.get("guidelines", []),
        )

    def _infer_treatment_category(self, treatment_type: str) -> TreatmentCategory:
        """Infer treatment category from treatment type string."""
        treatment_lower = treatment_type.lower()

        if any(x in treatment_lower for x in ["tki", "inhibitor", "targeted"]):
            return TreatmentCategory.TARGETED_THERAPY
        elif any(x in treatment_lower for x in ["immuno", "pd-1", "pd-l1", "ctla"]):
            return TreatmentCategory.IMMUNOTHERAPY
        elif "chemo" in treatment_lower:
            return TreatmentCategory.CHEMOTHERAPY
        elif any(x in treatment_lower for x in ["hormone", "endocrine"]):
            return TreatmentCategory.HORMONE_THERAPY
        else:
            return TreatmentCategory.TARGETED_THERAPY

    def _is_actionable_biomarker(self, biomarker: str, value: Any, tumor_type: str) -> bool:
        """Check if a biomarker is actionable."""
        actionable_biomarkers = {
            "PD_L1_high": lambda v: v
            and (v == "high" or (isinstance(v, (int, float)) and v >= 50)),
            "MSI_H": lambda v: v == "MSI-H" or v == "high" or v is True,
            "TMB_high": lambda v: isinstance(v, (int, float)) and v >= 10,
            "HER2_positive": lambda v: v == "positive" or v == "3+" or v is True,
            "HR_positive": lambda v: v == "positive" or v is True,
        }

        check_func = actionable_biomarkers.get(biomarker)
        if check_func:
            return check_func(value)

        return False

    def assess_risk(
        self,
        tumor_type: str,
        stage: str,
        molecular_profile: dict[str, Any],
        clinical_factors: dict | None = None,
    ) -> RiskAssessment:
        """Assess patient risk based on clinical and molecular factors.

        Args:
            tumor_type: Cancer type
            stage: Cancer stage
            molecular_profile: Molecular testing results
            clinical_factors: Additional clinical factors

        Returns:
            RiskAssessment

        """
        risk_factors = []
        protective_factors = []
        risk_score = 0.0

        # Stage-based risk
        stage_risk = {"I": 0.2, "II": 0.4, "III": 0.6, "IV": 0.8}
        stage_num = stage.upper().replace("STAGE", "").strip()
        risk_score += stage_risk.get(stage_num, 0.5)

        if stage_num in ["III", "IV"]:
            risk_factors.append(f"Advanced stage ({stage})")

        # Molecular risk factors
        mutations = molecular_profile.get("mutations", [])
        high_risk_genes = ["TP53", "PIK3CA", "KRAS", "BRAF"]

        for mutation in mutations:
            gene = mutation.get("gene")
            if gene in high_risk_genes:
                risk_factors.append(f"{gene} mutation")
                risk_score += 0.1

        # Protective factors
        biomarkers = molecular_profile.get("biomarkers", {})
        if biomarkers.get("MSI_H"):
            protective_factors.append("MSI-H status (favorable for immunotherapy)")
            risk_score -= 0.1

        # Clinical factors
        if clinical_factors:
            age = clinical_factors.get("age", 50)
            if age > 70:
                risk_factors.append("Age > 70")
                risk_score += 0.1

            ps = clinical_factors.get("performance_status", 0)
            if ps >= 2:
                risk_factors.append(f"Poor performance status (PS {ps})")
                risk_score += 0.2

        # Normalize risk score
        risk_score = max(0.0, min(1.0, risk_score))

        # Determine risk level
        if risk_score >= 0.7:
            risk_level = "high"
        elif risk_score >= 0.4:
            risk_level = "intermediate"
        else:
            risk_level = "low"

        # Generate recommendations
        recommendations = []
        if risk_level == "high":
            recommendations.append("Consider aggressive multimodal therapy")
            recommendations.append("Recommend clinical trial enrollment")
        elif risk_level == "intermediate":
            recommendations.append("Standard of care therapy recommended")
            recommendations.append("Consider genomic profiling for additional options")
        else:
            recommendations.append("Standard surveillance protocol")

        return RiskAssessment(
            risk_level=risk_level,
            risk_score=risk_score,
            risk_factors=risk_factors,
            protective_factors=protective_factors,
            recommendations=recommendations,
        )

    def generate_clinical_report(
        self,
        patient_id: str,
        tumor_type: str,
        molecular_profile: dict[str, Any],
        stage: str | None = None,
        clinical_factors: dict | None = None,
    ) -> ClinicalReport:
        """Generate a complete clinical decision support report.

        Args:
            patient_id: Patient identifier
            tumor_type: Cancer type
            molecular_profile: Molecular testing results
            stage: Cancer stage
            clinical_factors: Additional clinical factors

        Returns:
            ClinicalReport

        """
        # Generate treatment recommendations
        recommendations = self.generate_recommendations(
            tumor_type, molecular_profile, clinical_factors
        )

        # Assess risk
        risk_assessment = None
        if stage:
            risk_assessment = self.assess_risk(
                tumor_type, stage, molecular_profile, clinical_factors
            )

        # Extract actionable mutations
        actionable_mutations = []
        for mutation in molecular_profile.get("mutations", []):
            gene = mutation.get("gene")
            variant = mutation.get("protein_change")

            # Check if actionable
            biomarker_key = f"{gene}_{variant}" if variant else f"{gene}_mutation"
            if self.guidelines.get_guidelines_for_biomarker(tumor_type, biomarker_key):
                actionable_mutations.append(
                    {
                        "gene": gene,
                        "variant": variant,
                        "actionability": (
                            "Tier 1"
                            if any(
                                r.evidence[0].level in ["1", "2"]
                                for r in recommendations
                                if gene in str(r.biomarkers)
                            )
                            else "Tier 2"
                        ),
                    }
                )

        clinical_trials = self._find_clinical_trials(tumor_type, molecular_profile)

        return ClinicalReport(
            patient_id=patient_id,
            tumor_type=tumor_type,
            molecular_profile=molecular_profile,
            treatment_recommendations=recommendations,
            clinical_trials=clinical_trials,
            risk_assessment=risk_assessment,
            actionable_mutations=actionable_mutations,
            report_date=utc_now(),
        )

    def _find_clinical_trials(
        self,
        tumor_type: str,
        molecular_profile: dict[str, Any],
    ) -> list[dict]:
        """Query ClinicalTrials.gov v2 (public JSON) with a heuristic query; fall back locally if offline."""
        terms: list[str] = []
        if tumor_type:
            terms.extend(tumor_type.replace("_", " ").split())
        for mut in molecular_profile.get("mutations", [])[:6]:
            gene = mut.get("gene")
            if gene:
                terms.append(str(gene))
        query = " ".join(terms).strip() or "cancer interventional"

        params = urllib.parse.urlencode(
            {
                "query.term": query,
                "pageSize": "8",
                "format": "json",
            }
        )
        url = f"https://clinicaltrials.gov/api/v2/studies?{params}"
        try:
            with urllib.request.urlopen(url, timeout=15) as resp:
                payload = json.loads(resp.read().decode())
        except (
            urllib.error.URLError,
            urllib.error.HTTPError,
            TimeoutError,
            json.JSONDecodeError,
        ) as exc:
            logger.info("ClinicalTrials.gov request failed (%s); using local fallbacks", exc)
            return self._fallback_clinical_trials(molecular_profile)

        trials: list[dict[str, Any]] = []
        for study in payload.get("studies", [])[:8]:
            proto = study.get("protocolSection", {})
            ident = proto.get("identificationModule", {})
            status_mod = proto.get("statusModule", {})
            design = proto.get("designModule", {})
            phases = design.get("phases", []) if isinstance(design, dict) else []
            trials.append(
                {
                    "nct_id": ident.get("nctId"),
                    "title": ident.get("briefTitle") or ident.get("officialTitle"),
                    "status": status_mod.get("overallStatus"),
                    "phases": phases,
                    "query": query,
                }
            )
        return trials or self._fallback_clinical_trials(molecular_profile)

    def _fallback_clinical_trials(self, molecular_profile: dict[str, Any]) -> list[dict[str, Any]]:
        """Structured hints when the public API is unreachable."""
        out: list[dict[str, Any]] = []
        for mutation in molecular_profile.get("mutations", [])[:5]:
            gene = mutation.get("gene")
            if not gene:
                continue
            out.append(
                {
                    "nct_id": None,
                    "title": f"Search ClinicalTrials.gov for trials targeting {gene}",
                    "status": "unknown",
                    "biomarker": gene,
                    "note": "Populate when network access to clinicaltrials.gov is available",
                }
            )
        return out

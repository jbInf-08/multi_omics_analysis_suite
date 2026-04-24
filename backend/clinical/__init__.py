"""Clinical Analysis Module.
========================

Clinical annotation and decision support:
- COSMIC, ClinVar, OncoKB API integration
- Clinical decision support system
- Evidence-based recommendations
"""

from backend.clinical.annotation import (
    AnnotationResult,
    ClinicalAnnotator,
    ClinVarClient,
    COSMICClient,
    OncoKBClient,
)
from backend.clinical.decision_support import (
    ClinicalDecisionSupport,
    ClinicalEvidence,
    TreatmentRecommendation,
)

__all__ = [
    "ClinicalAnnotator",
    "COSMICClient",
    "ClinVarClient",
    "OncoKBClient",
    "AnnotationResult",
    "ClinicalDecisionSupport",
    "TreatmentRecommendation",
    "ClinicalEvidence",
]

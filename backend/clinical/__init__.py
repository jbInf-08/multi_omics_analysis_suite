"""
Clinical Analysis Module
========================

Clinical annotation and decision support:
- COSMIC, ClinVar, OncoKB API integration
- Clinical decision support system
- Evidence-based recommendations
"""

from backend.clinical.annotation import (
    ClinicalAnnotator,
    COSMICClient,
    ClinVarClient,
    OncoKBClient,
    AnnotationResult,
)
from backend.clinical.decision_support import (
    ClinicalDecisionSupport,
    TreatmentRecommendation,
    ClinicalEvidence,
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

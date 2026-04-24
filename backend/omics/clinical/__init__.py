"""
Clinical/Applied Omics Modules
==============================

Clinical and applied omics for medical applications:
- Immunogenomics
- Pharmacoproteomics
- Toxicogenomics
- Nutrigenomics
- Neurogenomics
- Allergomics
"""

from backend.omics.clinical.immunogenomics import ImmunogenomicsModule
from backend.omics.clinical.pharmacoproteomics import PharmacoproteomicsModule
from backend.omics.clinical.toxicogenomics import ToxicogenomicsModule
from backend.omics.clinical.nutrigenomics import NutrigenomicsModule
from backend.omics.clinical.neurogenomics import NeurogenomicsModule
from backend.omics.clinical.allergomics import AllergomicsModule

__all__ = [
    "ImmunogenomicsModule",
    "PharmacoproteomicsModule",
    "ToxicogenomicsModule",
    "NutrigenomicsModule",
    "NeurogenomicsModule",
    "AllergomicsModule",
]

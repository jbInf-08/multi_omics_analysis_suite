"""
Modification Omics Modules
==========================

Post-translational and chemical modification omics:
- Phosphoproteomics
- Glycomics
- Acetylomics
- Methylomics
- Ubiquitomics
- Kinomics
- Chromatomics
"""

from backend.omics.modifications.phosphoproteomics import PhosphoproteomicsModule
from backend.omics.modifications.glycomics import GlycomicsModule
from backend.omics.modifications.acetylomics import AcetylomicsModule
from backend.omics.modifications.methylomics import MethylomicsModule
from backend.omics.modifications.ubiquitomics import UbiquitomicsModule
from backend.omics.modifications.kinomics import KinomicsModule
from backend.omics.modifications.chromatomics import ChromatomicsModule

__all__ = [
    "PhosphoproteomicsModule",
    "GlycomicsModule",
    "AcetylomicsModule",
    "MethylomicsModule",
    "UbiquitomicsModule",
    "KinomicsModule",
    "ChromatomicsModule",
]

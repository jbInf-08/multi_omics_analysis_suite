"""
Core Omics Modules
==================

Fully implemented core omics modules:
- Genomics
- Transcriptomics
- Proteomics
- Metabolomics
- Epigenomics
- Metagenomics
- Pharmacogenomics
- Lipidomics
"""

from backend.omics.core.genomics import GenomicsModule
from backend.omics.core.transcriptomics import TranscriptomicsModule
from backend.omics.core.proteomics import ProteomicsModule
from backend.omics.core.metabolomics import MetabolomicsModule
from backend.omics.core.epigenomics import EpigenomicsModule
from backend.omics.core.metagenomics import MetagenomicsModule
from backend.omics.core.pharmacogenomics import PharmacogenomicsModule
from backend.omics.core.lipidomics import LipidomicsModule

__all__ = [
    "GenomicsModule",
    "TranscriptomicsModule",
    "ProteomicsModule",
    "MetabolomicsModule",
    "EpigenomicsModule",
    "MetagenomicsModule",
    "PharmacogenomicsModule",
    "LipidomicsModule",
]

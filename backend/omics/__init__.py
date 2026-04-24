"""Multi-Omics Analysis Suite - Omics Modules.
==========================================

This package contains all omics-specific modules covering 50+ omics disciplines.

Categories:
- Core: Genomics, Transcriptomics, Proteomics, Metabolomics, Epigenomics, Metagenomics, Pharmacogenomics, Lipidomics
- Modifications: Phosphoproteomics, Glycomics, Acetylomics, Methylomics, Ubiquitomics, Kinomics, Chromatomics
- Interactions: Interactomics, Connectomics, Synaptomics, Regulomics, Secretomics, Degradomics, Membranomics
- Clinical: Immunogenomics, Pharmacoproteomics, Toxicogenomics, Nutrigenomics, Neurogenomics, Allergomics
- Specialized: 20+ additional omics types
"""

from backend.omics.base.omics_base import OmicsCategory, OmicsModuleBase
from backend.omics.base.registry import OmicsRegistry

__all__ = ["OmicsRegistry", "OmicsModuleBase", "OmicsCategory"]

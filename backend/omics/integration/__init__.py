"""Multi-Omics Integration Module.
==============================

Data fusion and integration methods for multi-omics analysis:
- Early fusion (concatenation)
- Intermediate fusion (MOFA, JIVE)
- Late fusion (ensemble)
- Network-based integration (SNF)
- Pathway-based integration
"""

from backend.omics.integration.data_fusion import (
    DataFusion,
    EarlyFusion,
    IntermediateFusion,
    LateFusion,
)
from backend.omics.integration.network_integration import (
    NetworkIntegrator,
    SimilarityNetworkFusion,
)
from backend.omics.integration.pathway_integration import PathwayIntegrator

__all__ = [
    "DataFusion",
    "EarlyFusion",
    "IntermediateFusion",
    "LateFusion",
    "SimilarityNetworkFusion",
    "NetworkIntegrator",
    "PathwayIntegrator",
]

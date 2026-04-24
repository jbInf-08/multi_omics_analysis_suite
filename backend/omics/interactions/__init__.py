"""Interaction Omics Modules.
=========================

Molecular interaction and network omics:
- Interactomics (protein-protein interactions)
- Connectomics (neural connectivity)
- Synaptomics (synaptic connections)
- Regulomics (regulatory networks)
- Secretomics (secreted proteins)
- Degradomics (proteolytic processing)
- Membranomics (membrane proteomics)
"""

from backend.omics.interactions.connectomics import ConnectomicsModule
from backend.omics.interactions.degradomics import DegradomicsModule
from backend.omics.interactions.interactomics import InteractomicsModule
from backend.omics.interactions.membranomics import MembranomicsModule
from backend.omics.interactions.regulomics import RegulomicsModule
from backend.omics.interactions.secretomics import SecretomicsModule
from backend.omics.interactions.synaptomics import SynaptomicsModule

__all__ = [
    "InteractomicsModule",
    "ConnectomicsModule",
    "SynaptomicsModule",
    "RegulomicsModule",
    "SecretomicsModule",
    "DegradomicsModule",
    "MembranomicsModule",
]

"""Specialized Omics Modules.
=========================

Specialized and emerging omics disciplines including spatial,
single-cell, structural, temporal, and environmental omics.
"""

from .antibodyomics import AntibodyomicsModule

# Additional specialized modules
from .bibliomics import BibliomicsModule
from .cytomics import CytomicsModule
from .dynomics import DynomicsModule
from .editomics import EditomicsModule
from .embryomics import EmbryomicsModule
from .exposomics import ExposomicsModule
from .fluxomics import FluxomicsModule
from .foodomics import FoodomicsModule
from .glycoproteomics import GlycoproteomicsModule
from .hologenomics import HologenomicsModule
from .interferomics import InterferomicsModule
from .ionomics import IonomicsModule
from .mechanomics import MechanomicsModule
from .metallomics import MetallomicsModule
from .microbiomics import MicrobiomicsModule
from .multiomics_single_cell import MultiomicsSingleCellModule
from .obesomics import ObesomicsModule
from .organomics import OrganomicsModule
from .paleogenomics import PaleogenomicsModule
from .parvomics import ParvomicsModule
from .phenomics import PhenomicsModule
from .physiomics import PhysiomicsModule
from .radiomics import RadiomicsModule
from .researchomics import ResearchomicsModule
from .singlecell import SingleCellModule
from .spatialomics import SpatialomicsModule
from .speechomics import SpeechomicsModule
from .structuromics import StructuromicsModule
from .synthetomics import SynthetomicsModule
from .toponomics import ToponomicsModule
from .toxomics import ToxomicsModule
from .trialomics import TrialomicsModule
from .volatilomics import VolatilomicsModule

__all__ = [
    # Original specialized modules
    "SpatialomicsModule",
    "SingleCellModule",
    "StructuromicsModule",
    "ExposomicsModule",
    "RadiomicsModule",
    "PhenomicsModule",
    "FluxomicsModule",
    "FoodomicsModule",
    "IonomicsModule",
    "VolatilomicsModule",
    "GlycoproteomicsModule",
    "MetallomicsModule",
    "MicrobiomicsModule",
    "PaleogenomicsModule",
    "MultiomicsSingleCellModule",
    # Additional specialized modules
    "BibliomicsModule",
    "CytomicsModule",
    "EditomicsModule",
    "HologenomicsModule",
    "ObesomicsModule",
    "OrganomicsModule",
    "ParvomicsModule",
    "PhysiomicsModule",
    "SpeechomicsModule",
    "SynthetomicsModule",
    "ToponomicsModule",
    "ToxomicsModule",
    "AntibodyomicsModule",
    "EmbryomicsModule",
    "InterferomicsModule",
    "MechanomicsModule",
    "ResearchomicsModule",
    "TrialomicsModule",
    "DynomicsModule",
]

"""
Genome Assembly Module
======================

Comprehensive genome assembly tools for de novo assembly,
reference-guided assembly, scaffolding, and assembly quality assessment.
"""

from .assemblers import (
    Contig,
    AssemblyResult,
    AssemblyGraph,
    DeNovoAssembler,
    DeBruijnAssembler,
    OverlapLayoutConsensus,
    ReferenceGuidedAssembler,
    HybridAssembler,
)
from .scaffolding import (
    Scaffold,
    ScaffoldGraph,
    Scaffolder,
    GapFiller,
)
from .polishing import (
    ConsensusPolisher,
    ErrorCorrector,
    HomopolymerCorrector,
)
from .quality import (
    AssemblyQC,
    QUASTResult,
    BUSCOAnalysis,
    ContigStatistics,
)
from .graph import (
    ContigGraph,
    UnitGraph,
)

__all__ = [
    # Assemblers
    "Contig",
    "AssemblyResult",
    "AssemblyGraph",
    "DeNovoAssembler",
    "DeBruijnAssembler",
    "OverlapLayoutConsensus",
    "ReferenceGuidedAssembler",
    "HybridAssembler",
    # Scaffolding
    "Scaffold",
    "ScaffoldGraph",
    "Scaffolder",
    "GapFiller",
    # Polishing
    "ConsensusPolisher",
    "ErrorCorrector",
    "HomopolymerCorrector",
    # Quality
    "AssemblyQC",
    "QUASTResult",
    "BUSCOAnalysis",
    "ContigStatistics",
    # Graphs
    "ContigGraph",
    "UnitGraph",
]

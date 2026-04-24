"""Genome Assembly Module.
======================

Comprehensive genome assembly tools for de novo assembly,
reference-guided assembly, scaffolding, and assembly quality assessment.
"""

from .assemblers import (
    AssemblyGraph,
    AssemblyResult,
    Contig,
    DeBruijnAssembler,
    DeNovoAssembler,
    HybridAssembler,
    OverlapLayoutConsensus,
    ReferenceGuidedAssembler,
)
from .graph import (
    ContigGraph,
    UnitGraph,
)
from .polishing import (
    ConsensusPolisher,
    ErrorCorrector,
    HomopolymerCorrector,
)
from .quality import (
    AssemblyQC,
    BUSCOAnalysis,
    ContigStatistics,
    QUASTResult,
)
from .scaffolding import (
    GapFiller,
    Scaffold,
    Scaffolder,
    ScaffoldGraph,
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

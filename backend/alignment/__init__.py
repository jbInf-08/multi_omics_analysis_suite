"""Read Alignment Module.
=====================

Comprehensive read alignment tools for short and long read mapping,
alignment processing, and variant calling preparation.
"""

from .bam import (
    BAMProcessor,
    BaseRecalibrator,
    CoverageCalculator,
    DuplicateMarker,
    PileupGenerator,
)
from .index import (
    FMIndex,
    HashIndex,
    MinimapIndex,
    ReferenceIndex,
)
from .mappers import (
    Aligner,
    AlignmentResult,
    BurrowsWheelerAligner,
    LongReadMapper,
    MiniMap2Aligner,
    ShortReadMapper,
    SplicedAligner,
)
from .quality import (
    AlignmentQC,
    CoverageAnalysis,
    InsertSizeDistribution,
    MappingStatistics,
)
from .sam import (
    CIGARParser,
    SAMHeader,
    SAMReader,
    SAMRecord,
    SAMWriter,
)

__all__ = [
    # Mappers
    "Aligner",
    "BurrowsWheelerAligner",
    "MiniMap2Aligner",
    "ShortReadMapper",
    "LongReadMapper",
    "SplicedAligner",
    "AlignmentResult",
    # Index
    "ReferenceIndex",
    "FMIndex",
    "MinimapIndex",
    "HashIndex",
    # SAM
    "SAMRecord",
    "SAMHeader",
    "SAMReader",
    "SAMWriter",
    "CIGARParser",
    # BAM
    "BAMProcessor",
    "PileupGenerator",
    "CoverageCalculator",
    "DuplicateMarker",
    "BaseRecalibrator",
    # Quality
    "AlignmentQC",
    "MappingStatistics",
    "InsertSizeDistribution",
    "CoverageAnalysis",
]

"""
Read Alignment Module
=====================

Comprehensive read alignment tools for short and long read mapping,
alignment processing, and variant calling preparation.
"""

from .mappers import (
    Aligner,
    BurrowsWheelerAligner,
    MiniMap2Aligner,
    ShortReadMapper,
    LongReadMapper,
    SplicedAligner,
    AlignmentResult,
)
from .index import (
    ReferenceIndex,
    FMIndex,
    MinimapIndex,
    HashIndex,
)
from .sam import (
    SAMRecord,
    SAMHeader,
    SAMReader,
    SAMWriter,
    CIGARParser,
)
from .bam import (
    BAMProcessor,
    PileupGenerator,
    CoverageCalculator,
    DuplicateMarker,
    BaseRecalibrator,
)
from .quality import (
    AlignmentQC,
    MappingStatistics,
    InsertSizeDistribution,
    CoverageAnalysis,
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

"""Long Read Sequencing Module.
===========================

Analysis tools for Oxford Nanopore and PacBio sequencing data.
"""

from .analysis import (
    AdapterDetector,
    ErrorProfile,
    LongReadQC,
    QualityAnalysis,
    ReadLengthDistribution,
)
from .basecalling import (
    BaseCaller,
    NanoporeBaseCaller,
    QualityScoreCalculator,
    SignalProcessor,
)
from .methylation import (
    DamageDetector,
    MethylationCaller,
    ModificationDetector,
)
from .phasing import (
    HaplotypeAssembler,
    Phaser,
    ReadPartitioner,
)
from .structural_variants import (
    BreakpointDetector,
    DeletionFinder,
    InsertionFinder,
    InversionFinder,
    SVCaller,
    TranslocationFinder,
)
from .transcript import (
    AlternativeSplicing,
    FullLengthTranscript,
    IsoformDetector,
)

__all__ = [
    # Basecalling
    "BaseCaller",
    "NanoporeBaseCaller",
    "SignalProcessor",
    "QualityScoreCalculator",
    # Analysis
    "LongReadQC",
    "ReadLengthDistribution",
    "QualityAnalysis",
    "ErrorProfile",
    "AdapterDetector",
    # Methylation
    "MethylationCaller",
    "ModificationDetector",
    "DamageDetector",
    # SVs
    "SVCaller",
    "BreakpointDetector",
    "InsertionFinder",
    "DeletionFinder",
    "InversionFinder",
    "TranslocationFinder",
    # Phasing
    "Phaser",
    "HaplotypeAssembler",
    "ReadPartitioner",
    # Transcripts
    "IsoformDetector",
    "FullLengthTranscript",
    "AlternativeSplicing",
]

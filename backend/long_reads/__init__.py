"""
Long Read Sequencing Module
===========================

Analysis tools for Oxford Nanopore and PacBio sequencing data.
"""

from .basecalling import (
    BaseCaller,
    NanoporeBaseCaller,
    SignalProcessor,
    QualityScoreCalculator,
)
from .analysis import (
    LongReadQC,
    ReadLengthDistribution,
    QualityAnalysis,
    ErrorProfile,
    AdapterDetector,
)
from .methylation import (
    MethylationCaller,
    ModificationDetector,
    DamageDetector,
)
from .structural_variants import (
    SVCaller,
    BreakpointDetector,
    InsertionFinder,
    DeletionFinder,
    InversionFinder,
    TranslocationFinder,
)
from .phasing import (
    Phaser,
    HaplotypeAssembler,
    ReadPartitioner,
)
from .transcript import (
    IsoformDetector,
    FullLengthTranscript,
    AlternativeSplicing,
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

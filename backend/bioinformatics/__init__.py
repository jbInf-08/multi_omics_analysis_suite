"""
Bioinformatics Foundation Module
================================

Core bioinformatics utilities, algorithms, and data structures for
sequence analysis, alignment, and biological computations.
"""

from .sequence import (
    Sequence,
    DNASequence,
    RNASequence,
    ProteinSequence,
    SequenceCollection,
)
from .algorithms import (
    SequenceAligner,
    LocalAligner,
    GlobalAligner,
    MultipleSequenceAligner,
    MotifFinder,
    KmerCounter,
)
from .formats import (
    FastaParser,
    FastqParser,
    GFFParser,
    BEDParser,
    SAMParser,
    VCFParser,
    GenBankParser,
)
from .utils import (
    reverse_complement,
    translate,
    gc_content,
    calculate_tm,
    find_orfs,
    codon_usage,
)

__all__ = [
    # Sequences
    "Sequence",
    "DNASequence",
    "RNASequence", 
    "ProteinSequence",
    "SequenceCollection",
    # Algorithms
    "SequenceAligner",
    "LocalAligner",
    "GlobalAligner",
    "MultipleSequenceAligner",
    "MotifFinder",
    "KmerCounter",
    # Parsers
    "FastaParser",
    "FastqParser",
    "GFFParser",
    "BEDParser",
    "SAMParser",
    "VCFParser",
    "GenBankParser",
    # Utilities
    "reverse_complement",
    "translate",
    "gc_content",
    "calculate_tm",
    "find_orfs",
    "codon_usage",
]

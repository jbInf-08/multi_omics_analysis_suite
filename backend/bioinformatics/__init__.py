"""Bioinformatics Foundation Module.
================================

Core bioinformatics utilities, algorithms, and data structures for
sequence analysis, alignment, and biological computations.
"""

from .algorithms import (
    GlobalAligner,
    KmerCounter,
    LocalAligner,
    MotifFinder,
    MultipleSequenceAligner,
    SequenceAligner,
)
from .formats import (
    BEDParser,
    FastaParser,
    FastqParser,
    GenBankParser,
    GFFParser,
    SAMParser,
    VCFParser,
)
from .sequence import (
    DNASequence,
    ProteinSequence,
    RNASequence,
    Sequence,
    SequenceCollection,
)
from .utils import (
    calculate_tm,
    codon_usage,
    find_orfs,
    gc_content,
    reverse_complement,
    translate,
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

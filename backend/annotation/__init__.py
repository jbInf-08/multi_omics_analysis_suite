"""
Genome Annotation Module
========================

Comprehensive genome annotation including gene prediction, functional
annotation, and structural annotation.
"""

from .gene_prediction import (
    GenePrediction,
    GenePredictor,
    ProdigalPredictor,
    AugustusPredictor,
    GlimmerPredictor,
    MetaGenePredictor,
    ORFFinder,
)
from .functional import (
    FunctionalAnnotation,
    FunctionalAnnotator,
    BlastAnnotator,
    HMMAnnotator,
    InterProAnnotator,
    GOAnnotator,
    KEGGAnnotator,
    COGAnnotator,
    ECNumberAnnotator,
)
from .structural import (
    StructuralAnnotation,
    RepeatFinder,
    tRNAScanner,
    rRNAFinder,
    ncRNAFinder,
    CRISPRFinder,
    PromoterFinder,
    TerminatorFinder,
)
from .comparative import (
    SyntenyAnalyzer,
    OrthologFinder,
    GeneCluster,
)

__all__ = [
    # Gene Prediction
    "GenePrediction",
    "GenePredictor",
    "ProdigalPredictor",
    "AugustusPredictor",
    "GlimmerPredictor",
    "MetaGenePredictor",
    "ORFFinder",
    # Functional Annotation
    "FunctionalAnnotation",
    "FunctionalAnnotator",
    "BlastAnnotator",
    "HMMAnnotator",
    "InterProAnnotator",
    "GOAnnotator",
    "KEGGAnnotator",
    "COGAnnotator",
    "ECNumberAnnotator",
    # Structural Annotation
    "StructuralAnnotation",
    "RepeatFinder",
    "tRNAScanner",
    "rRNAFinder",
    "ncRNAFinder",
    "CRISPRFinder",
    "PromoterFinder",
    "TerminatorFinder",
    # Comparative
    "SyntenyAnalyzer",
    "OrthologFinder",
    "GeneCluster",
]

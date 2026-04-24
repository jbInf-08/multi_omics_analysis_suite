"""Genome Annotation Module.
========================

Comprehensive genome annotation including gene prediction, functional
annotation, and structural annotation.
"""

from .comparative import (
    GeneCluster,
    OrthologFinder,
    SyntenyAnalyzer,
)
from .functional import (
    BlastAnnotator,
    COGAnnotator,
    ECNumberAnnotator,
    FunctionalAnnotation,
    FunctionalAnnotator,
    GOAnnotator,
    HMMAnnotator,
    InterProAnnotator,
    KEGGAnnotator,
)
from .gene_prediction import (
    AugustusPredictor,
    GenePrediction,
    GenePredictor,
    GlimmerPredictor,
    MetaGenePredictor,
    ORFFinder,
    ProdigalPredictor,
)
from .structural import (
    CRISPRFinder,
    PromoterFinder,
    RepeatFinder,
    StructuralAnnotation,
    TerminatorFinder,
    ncRNAFinder,
    rRNAFinder,
    tRNAScanner,
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

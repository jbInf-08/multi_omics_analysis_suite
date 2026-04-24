"""Multi-Omics Analysis Suite - Analysis Modules.
==============================================

Comprehensive analysis pipelines including:
- Biomarker Discovery Pipeline
- Statistical Analysis Pipeline
- Survival Analysis Module
- Pathway Analysis (GSEA, ORA)
- R Integration (DESeq2, edgeR, limma)
"""

from backend.analysis.biomarker_discovery import (
    BiomarkerDiscoveryPipeline,
    ConsensusScorer,
    StabilitySelector,
)
from backend.analysis.pathway_analysis import (
    GSEAAnalyzer,
    ORAAnalyzer,
    PathwayAnalysisPipeline,
)
from backend.analysis.r_integration import (
    DESeq2Analyzer,
    EdgeRAnalyzer,
    LimmaAnalyzer,
    RIntegrationManager,
)
from backend.analysis.statistical_analysis import (
    EffectSizeCalculator,
    MultipleTestingCorrection,
    StatisticalAnalysisPipeline,
)
from backend.analysis.survival_analysis import (
    CoxProportionalHazards,
    KaplanMeierEstimator,
    SurvivalAnalysisPipeline,
)

__all__ = [
    # Biomarker Discovery
    "BiomarkerDiscoveryPipeline",
    "ConsensusScorer",
    "StabilitySelector",
    # Statistical Analysis
    "StatisticalAnalysisPipeline",
    "EffectSizeCalculator",
    "MultipleTestingCorrection",
    # Survival Analysis
    "SurvivalAnalysisPipeline",
    "CoxProportionalHazards",
    "KaplanMeierEstimator",
    # Pathway Analysis
    "PathwayAnalysisPipeline",
    "GSEAAnalyzer",
    "ORAAnalyzer",
    # R Integration
    "RIntegrationManager",
    "DESeq2Analyzer",
    "EdgeRAnalyzer",
    "LimmaAnalyzer",
]

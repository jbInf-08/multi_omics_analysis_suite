"""Data Collection Framework.
=========================

Comprehensive data collection system with 100+ source collectors:
- Master orchestrator for coordinated collection
- Parallel processing with retry logic
- Support for genomic, clinical, imaging, and literature sources
"""

from backend.data_collection.base_collector import (
    BaseCollector,
    CollectionResult,
    CollectorConfig,
    DataSource,
)
from backend.data_collection.master_orchestrator import (
    CollectionPlan,
    MasterOrchestrator,
    OrchestratorConfig,
)

__all__ = [
    "BaseCollector",
    "CollectorConfig",
    "CollectionResult",
    "DataSource",
    "MasterOrchestrator",
    "CollectionPlan",
    "OrchestratorConfig",
]

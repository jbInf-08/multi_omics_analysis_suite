"""
Workflow Orchestration Module
=============================

Integration with workflow engines:
- Nextflow pipelines
- Snakemake workflows
"""

from backend.workflows.nextflow_integration import (
    NextflowRunner,
    NextflowPipeline,
    NextflowConfig,
)
from backend.workflows.snakemake_manager import (
    SnakemakeRunner,
    SnakemakeWorkflow,
    SnakemakeConfig,
)

__all__ = [
    "NextflowRunner",
    "NextflowPipeline", 
    "NextflowConfig",
    "SnakemakeRunner",
    "SnakemakeWorkflow",
    "SnakemakeConfig",
]

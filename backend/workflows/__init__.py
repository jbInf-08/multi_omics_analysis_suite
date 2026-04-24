"""Workflow Orchestration Module.
=============================

Integration with workflow engines:
- Nextflow pipelines
- Snakemake workflows
"""

from backend.workflows.nextflow_integration import (
    NextflowConfig,
    NextflowPipeline,
    NextflowRunner,
)
from backend.workflows.snakemake_manager import (
    SnakemakeConfig,
    SnakemakeRunner,
    SnakemakeWorkflow,
)

__all__ = [
    "NextflowRunner",
    "NextflowPipeline",
    "NextflowConfig",
    "SnakemakeRunner",
    "SnakemakeWorkflow",
    "SnakemakeConfig",
]

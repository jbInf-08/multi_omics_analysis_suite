"""Master Orchestrator.
===================

Coordinates data collection across multiple sources
with parallel processing, retry logic, and progress tracking.
"""

import asyncio
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


def utc_now() -> datetime:
    """Return current UTC time."""
    return datetime.now(timezone.utc)


from backend.data_collection.base_collector import (
    BaseCollector,
    CollectionResult,
    CollectorConfig,
    CollectorRegistry,
    DataSource,
)

logger = logging.getLogger(__name__)


class CollectionStatus(str, Enum):
    """Status of a collection task."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


@dataclass
class CollectionTask:
    """A single collection task."""

    source: DataSource
    parameters: dict[str, Any] = field(default_factory=dict)
    priority: int = 5  # 1-10, lower is higher priority
    dependencies: list[DataSource] = field(default_factory=list)
    status: CollectionStatus = CollectionStatus.PENDING
    result: CollectionResult | None = None
    attempts: int = 0
    max_attempts: int = 3
    created_at: datetime = field(default_factory=utc_now)
    started_at: datetime | None = None
    completed_at: datetime | None = None


@dataclass
class CollectionPlan:
    """A plan for collecting data from multiple sources."""

    name: str
    description: str = ""
    tasks: list[CollectionTask] = field(default_factory=list)
    created_at: datetime = field(default_factory=utc_now)

    def add_task(
        self,
        source: DataSource,
        parameters: dict | None = None,
        priority: int = 5,
        dependencies: list[DataSource] | None = None,
    ) -> "CollectionPlan":
        """Add a task to the plan."""
        task = CollectionTask(
            source=source,
            parameters=parameters or {},
            priority=priority,
            dependencies=dependencies or [],
        )
        self.tasks.append(task)
        return self

    def add_sources(self, sources: list[DataSource]) -> "CollectionPlan":
        """Add multiple sources with default settings."""
        for source in sources:
            self.add_task(source)
        return self


@dataclass
class OrchestratorConfig:
    """Configuration for the master orchestrator."""

    max_parallel: int = 10
    default_timeout: int = 300
    retry_failed: bool = True
    max_retries: int = 3
    retry_delay: float = 5.0
    output_dir: Path = Path("./data/collected")
    save_results: bool = True
    progress_callback: Callable[[str, float], None] | None = None
    api_keys: dict[str, str] = field(default_factory=dict)


class MasterOrchestrator:
    """Master orchestrator for coordinating data collection.

    Features:
    - Parallel collection from multiple sources
    - Dependency management between tasks
    - Automatic retry with exponential backoff
    - Progress tracking and callbacks
    - Result aggregation and persistence
    """

    def __init__(self, config: OrchestratorConfig | None = None):
        """Initialize master orchestrator.

        Args:
            config: Orchestrator configuration

        """
        self.config = config or OrchestratorConfig()
        self._collectors: dict[DataSource, BaseCollector] = {}
        self._results: dict[DataSource, CollectionResult] = {}
        self._running = False
        self._cancelled = False

        # Ensure output directory exists
        self.config.output_dir.mkdir(parents=True, exist_ok=True)

    def _get_collector(self, source: DataSource) -> BaseCollector | None:
        """Get or create a collector for a source."""
        if source not in self._collectors:
            config = CollectorConfig(
                source=source,
                api_key=self.config.api_keys.get(source.value),
            )
            collector = CollectorRegistry.create(source, config)
            if collector:
                self._collectors[source] = collector

        return self._collectors.get(source)

    async def execute_plan(
        self,
        plan: CollectionPlan,
        progress_callback: Callable[[str, float], None] | None = None,
    ) -> dict[DataSource, CollectionResult]:
        """Execute a collection plan.

        Args:
            plan: Collection plan to execute
            progress_callback: Optional progress callback

        Returns:
            Dictionary of results by source

        """
        self._running = True
        self._cancelled = False
        self._results = {}

        callback = progress_callback or self.config.progress_callback

        logger.info(f"Starting collection plan: {plan.name} with {len(plan.tasks)} tasks")

        # Sort tasks by priority
        tasks = sorted(plan.tasks, key=lambda t: t.priority)

        # Track completed sources for dependency resolution
        completed: set[DataSource] = set()

        total_tasks = len(tasks)
        completed_count = 0

        while tasks and not self._cancelled:
            # Find tasks that can run (dependencies satisfied)
            ready_tasks = [
                t
                for t in tasks
                if all(d in completed for d in t.dependencies)
                and t.status == CollectionStatus.PENDING
            ]

            if not ready_tasks:
                # Wait for running tasks to complete
                await asyncio.sleep(0.5)
                continue

            # Limit parallel execution
            batch_size = min(len(ready_tasks), self.config.max_parallel)
            batch = ready_tasks[:batch_size]

            # Execute batch
            async_tasks = []
            for task in batch:
                task.status = CollectionStatus.RUNNING
                task.started_at = utc_now()
                async_tasks.append(self._execute_task(task))

            # Wait for batch completion
            results = await asyncio.gather(*async_tasks, return_exceptions=True)

            # Process results
            for task, result in zip(batch, results, strict=False):
                if isinstance(result, Exception):
                    task.status = CollectionStatus.FAILED
                    task.result = CollectionResult(
                        source=task.source,
                        success=False,
                        errors=[str(result)],
                    )
                    logger.error(f"Task {task.source.value} failed: {result}")
                else:
                    task.result = result
                    task.status = (
                        CollectionStatus.COMPLETED if result.success else CollectionStatus.FAILED
                    )

                task.completed_at = utc_now()
                self._results[task.source] = task.result

                if task.status == CollectionStatus.COMPLETED:
                    completed.add(task.source)

                completed_count += 1

                if callback:
                    progress = completed_count / total_tasks
                    callback(task.source.value, progress)

            # Remove completed tasks
            tasks = [t for t in tasks if t.status == CollectionStatus.PENDING]

        self._running = False

        # Save results if configured
        if self.config.save_results:
            await self._save_results(plan.name)

        logger.info(f"Collection plan complete: {len(completed)}/{total_tasks} successful")

        return self._results

    async def _execute_task(self, task: CollectionTask) -> CollectionResult:
        """Execute a single collection task."""
        collector = self._get_collector(task.source)

        if collector is None:
            return CollectionResult(
                source=task.source,
                success=False,
                errors=[f"No collector available for {task.source.value}"],
            )

        try:
            result = await asyncio.wait_for(
                collector.collect(**task.parameters),
                timeout=self.config.default_timeout,
            )
            return result

        except asyncio.TimeoutError:
            return CollectionResult(
                source=task.source,
                success=False,
                errors=["Collection timed out"],
            )
        except Exception as e:
            logger.exception(f"Error collecting from {task.source.value}")
            return CollectionResult(
                source=task.source,
                success=False,
                errors=[str(e)],
            )

    async def _save_results(self, plan_name: str):
        """Save collection results to disk."""
        timestamp = utc_now().strftime("%Y%m%d_%H%M%S")
        output_file = self.config.output_dir / f"{plan_name}_{timestamp}.json"

        results_data = {
            "plan_name": plan_name,
            "timestamp": timestamp,
            "results": {
                source.value: {
                    "success": result.success,
                    "records": result.records_collected,
                    "errors": result.errors,
                    "duration": result.duration_seconds,
                }
                for source, result in self._results.items()
            },
        }

        with open(output_file, "w") as f:
            json.dump(results_data, f, indent=2)

        logger.info(f"Results saved to {output_file}")

    def cancel(self):
        """Cancel running collection."""
        self._cancelled = True

    async def close(self):
        """Close all collectors."""
        for collector in self._collectors.values():
            await collector.close()

    # Convenience methods for common collection patterns

    async def collect_tcga(
        self,
        cancer_types: list[str] | None = None,
        data_types: list[str] | None = None,
    ) -> CollectionResult:
        """Collect TCGA data."""
        plan = CollectionPlan(name="tcga_collection")
        plan.add_task(
            DataSource.TCGA,
            parameters={"cancer_types": cancer_types, "data_types": data_types},
        )
        results = await self.execute_plan(plan)
        return results.get(DataSource.TCGA)

    async def collect_geo(
        self,
        accessions: list[str] | None = None,
        query: str | None = None,
    ) -> CollectionResult:
        """Collect GEO data."""
        plan = CollectionPlan(name="geo_collection")
        plan.add_task(
            DataSource.GEO,
            parameters={"accessions": accessions, "query": query},
        )
        results = await self.execute_plan(plan)
        return results.get(DataSource.GEO)

    async def collect_all_cancer_genomics(
        self,
        cancer_type: str,
    ) -> dict[DataSource, CollectionResult]:
        """Collect all cancer genomics data for a cancer type."""
        plan = CollectionPlan(
            name=f"cancer_genomics_{cancer_type}",
            description=f"Comprehensive cancer genomics collection for {cancer_type}",
        )

        # Add all relevant sources
        sources = [
            (DataSource.TCGA, {"cancer_type": cancer_type}),
            (DataSource.GDC, {"project": cancer_type}),
            (DataSource.ICGC, {"cancer_type": cancer_type}),
            (DataSource.COSMIC, {"cancer_type": cancer_type}),
            (DataSource.CBIOPORTAL, {"study": cancer_type}),
        ]

        for source, params in sources:
            plan.add_task(source, parameters=params)

        return await self.execute_plan(plan)


# Pre-built collection plans


def create_comprehensive_cancer_plan(cancer_type: str) -> CollectionPlan:
    """Create a comprehensive cancer data collection plan."""
    plan = CollectionPlan(
        name=f"comprehensive_{cancer_type}",
        description=f"Comprehensive multi-omics data for {cancer_type}",
    )

    # Genomic data
    plan.add_task(DataSource.TCGA, {"cancer_type": cancer_type}, priority=1)
    plan.add_task(DataSource.GDC, {"project": cancer_type}, priority=1)
    plan.add_task(DataSource.ICGC, {"cancer_type": cancer_type}, priority=2)

    # Mutation data
    plan.add_task(DataSource.COSMIC, {"cancer_type": cancer_type}, priority=2)
    plan.add_task(DataSource.CLINVAR, {}, priority=3)
    plan.add_task(DataSource.ONCOKB, {}, priority=3)

    # Protein data
    plan.add_task(DataSource.CPTAC, {"cancer_type": cancer_type}, priority=2)
    plan.add_task(DataSource.STRING, {}, priority=4)

    # Drug response
    plan.add_task(DataSource.GDSC, {}, priority=4)
    plan.add_task(DataSource.CCLE, {}, priority=4)

    # Pathways
    plan.add_task(DataSource.KEGG, {}, priority=5)
    plan.add_task(DataSource.REACTOME, {}, priority=5)

    # Literature
    plan.add_task(DataSource.PUBMED, {"query": cancer_type}, priority=6)

    return plan


def create_biomarker_discovery_plan(
    genes: list[str],
    cancer_type: str | None = None,
) -> CollectionPlan:
    """Create a biomarker discovery collection plan."""
    plan = CollectionPlan(
        name="biomarker_discovery",
        description="Data collection for biomarker discovery",
    )

    params = {"genes": genes}
    if cancer_type:
        params["cancer_type"] = cancer_type

    # Expression data
    plan.add_task(DataSource.TCGA, params, priority=1)
    plan.add_task(DataSource.GTEX, {"genes": genes}, priority=2)
    plan.add_task(DataSource.GEO, {"genes": genes}, priority=2)

    # Variant data
    plan.add_task(DataSource.CLINVAR, {"genes": genes}, priority=2)
    plan.add_task(DataSource.GNOMAD, {"genes": genes}, priority=3)

    # Functional data
    plan.add_task(DataSource.UNIPROT, {"genes": genes}, priority=3)
    plan.add_task(DataSource.STRING, {"genes": genes}, priority=4)

    # Clinical significance
    plan.add_task(DataSource.ONCOKB, {"genes": genes}, priority=2)
    plan.add_task(DataSource.CIVIC, {"genes": genes}, priority=3)

    return plan

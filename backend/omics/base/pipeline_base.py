"""
Pipeline Base Classes
=====================

Base classes for analysis pipelines.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable, TypeVar, Generic
from datetime import datetime, timezone
from enum import Enum
import asyncio
import logging

from backend.omics.base.omics_base import OmicsData, AnalysisResult


logger = logging.getLogger(__name__)


class StepStatus(str, Enum):
    """Pipeline step status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PipelineContext:
    """
    Context passed between pipeline steps.
    
    Contains shared data, results, and configuration.
    """
    
    # Input data
    input_data: Dict[str, OmicsData] = field(default_factory=dict)
    
    # Intermediate results from each step
    step_results: Dict[str, Any] = field(default_factory=dict)
    
    # Global parameters
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    # Output artifacts
    artifacts: Dict[str, Any] = field(default_factory=dict)
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Progress tracking
    current_step: int = 0
    total_steps: int = 0
    progress: float = 0.0
    
    # Status
    status: str = "pending"
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def get_result(self, step_name: str) -> Optional[Any]:
        """Get result from a previous step."""
        return self.step_results.get(step_name)
    
    def set_result(self, step_name: str, result: Any):
        """Store result from a step."""
        self.step_results[step_name] = result
    
    def add_artifact(self, name: str, artifact: Any):
        """Add an output artifact."""
        self.artifacts[name] = artifact
    
    def update_progress(self, step: int, total: int):
        """Update progress."""
        self.current_step = step
        self.total_steps = total
        self.progress = step / total if total > 0 else 0.0


@dataclass
class StepResult:
    """Result from a pipeline step."""
    
    step_name: str
    status: StepStatus
    output: Any = None
    metrics: Dict[str, float] = field(default_factory=dict)
    duration: Optional[float] = None
    error: Optional[str] = None
    
    @property
    def success(self) -> bool:
        return self.status == StepStatus.COMPLETED


class PipelineStep(ABC):
    """
    Abstract base class for pipeline steps.
    
    Each step in a pipeline must implement:
    - name: Step name
    - execute: Step logic
    """
    
    def __init__(
        self,
        name: str,
        description: str = "",
        required: bool = True,
        dependencies: Optional[List[str]] = None,
    ):
        self.name = name
        self.description = description
        self.required = required
        self.dependencies = dependencies or []
    
    @abstractmethod
    async def execute(self, context: PipelineContext) -> StepResult:
        """
        Execute the pipeline step.
        
        Args:
            context: Pipeline context
            
        Returns:
            Step result
        """
        pass
    
    def validate_dependencies(self, context: PipelineContext) -> bool:
        """Check if all dependencies are satisfied."""
        for dep in self.dependencies:
            if dep not in context.step_results:
                return False
        return True
    
    async def run(self, context: PipelineContext) -> StepResult:
        """
        Run the step with error handling.
        
        Args:
            context: Pipeline context
            
        Returns:
            Step result
        """
        start_time = datetime.now(timezone.utc)
        
        try:
            # Check dependencies
            if not self.validate_dependencies(context):
                return StepResult(
                    step_name=self.name,
                    status=StepStatus.FAILED,
                    error="Dependencies not satisfied",
                )
            
            # Execute step
            result = await self.execute(context)
            result.duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            
            # Store result in context
            if result.success:
                context.set_result(self.name, result.output)
            
            return result
            
        except Exception as e:
            logger.exception(f"Step {self.name} failed: {e}")
            return StepResult(
                step_name=self.name,
                status=StepStatus.FAILED,
                error=str(e),
                duration=(datetime.now(timezone.utc) - start_time).total_seconds(),
            )


class PipelineBase(ABC):
    """
    Abstract base class for analysis pipelines.
    
    Pipelines orchestrate multiple steps to perform complex analyses.
    """
    
    def __init__(
        self,
        name: str,
        description: str = "",
        version: str = "1.0.0",
    ):
        self.name = name
        self.description = description
        self.version = version
        self.steps: List[PipelineStep] = []
        self._progress_callback: Optional[Callable] = None
    
    @abstractmethod
    def build_steps(self) -> List[PipelineStep]:
        """
        Build the list of pipeline steps.
        
        Returns:
            List of pipeline steps
        """
        pass
    
    def set_progress_callback(self, callback: Callable):
        """Set callback for progress updates."""
        self._progress_callback = callback
    
    async def _report_progress(
        self,
        context: PipelineContext,
        step_name: str,
        status: str,
    ):
        """Report progress to callback."""
        if self._progress_callback:
            await self._progress_callback(
                progress=context.progress,
                step=step_name,
                status=status,
            )
    
    async def run(
        self,
        context: PipelineContext,
        skip_steps: Optional[List[str]] = None,
    ) -> PipelineContext:
        """
        Run the pipeline.
        
        Args:
            context: Pipeline context
            skip_steps: Steps to skip
            
        Returns:
            Updated context with results
        """
        skip_steps = skip_steps or []
        
        # Build steps
        self.steps = self.build_steps()
        context.total_steps = len(self.steps)
        context.status = "running"
        
        logger.info(f"Starting pipeline '{self.name}' with {len(self.steps)} steps")
        
        for i, step in enumerate(self.steps):
            context.current_step = i + 1
            context.update_progress(i, len(self.steps))
            
            # Check if step should be skipped
            if step.name in skip_steps:
                logger.info(f"Skipping step: {step.name}")
                context.step_results[step.name] = StepResult(
                    step_name=step.name,
                    status=StepStatus.SKIPPED,
                )
                continue
            
            logger.info(f"Running step {i+1}/{len(self.steps)}: {step.name}")
            await self._report_progress(context, step.name, "running")
            
            # Run step
            result = await step.run(context)
            
            if not result.success:
                if step.required:
                    context.status = "failed"
                    context.errors.append(f"Step '{step.name}' failed: {result.error}")
                    logger.error(f"Pipeline failed at step: {step.name}")
                    await self._report_progress(context, step.name, "failed")
                    break
                else:
                    context.warnings.append(f"Optional step '{step.name}' failed: {result.error}")
                    logger.warning(f"Optional step failed: {step.name}")
            
            await self._report_progress(context, step.name, "completed")
        
        # Finalize
        if context.status != "failed":
            context.status = "completed"
            context.progress = 1.0
        
        logger.info(f"Pipeline '{self.name}' finished with status: {context.status}")
        
        return context
    
    def get_step(self, name: str) -> Optional[PipelineStep]:
        """Get step by name."""
        for step in self.steps:
            if step.name == name:
                return step
        return None


# Common pipeline steps
class LoadDataStep(PipelineStep):
    """Load data step."""
    
    def __init__(self, data_key: str = "input"):
        super().__init__(
            name="load_data",
            description="Load input data",
        )
        self.data_key = data_key
    
    async def execute(self, context: PipelineContext) -> StepResult:
        data = context.input_data.get(self.data_key)
        if data is None:
            return StepResult(
                step_name=self.name,
                status=StepStatus.FAILED,
                error=f"No input data found for key: {self.data_key}",
            )
        return StepResult(
            step_name=self.name,
            status=StepStatus.COMPLETED,
            output=data,
        )


class QualityControlStep(PipelineStep):
    """Quality control step."""
    
    def __init__(self, module, params: Optional[Dict] = None):
        super().__init__(
            name="quality_control",
            description="Run quality control checks",
            dependencies=["load_data"],
        )
        self.module = module
        self.params = params or {}
    
    async def execute(self, context: PipelineContext) -> StepResult:
        data = context.get_result("load_data")
        qc_report = self.module.quality_control(data, self.params)
        return StepResult(
            step_name=self.name,
            status=StepStatus.COMPLETED if qc_report.passed else StepStatus.FAILED,
            output=qc_report,
            metrics={"qc_passed": 1.0 if qc_report.passed else 0.0},
        )


class NormalizationStep(PipelineStep):
    """Normalization step."""
    
    def __init__(self, module, method: str = "quantile", params: Optional[Dict] = None):
        super().__init__(
            name="normalization",
            description=f"Normalize data using {method}",
            dependencies=["quality_control"],
        )
        self.module = module
        self.method = method
        self.params = params or {}
    
    async def execute(self, context: PipelineContext) -> StepResult:
        data = context.get_result("load_data")
        normalized = self.module.normalize(data, self.method, self.params)
        return StepResult(
            step_name=self.name,
            status=StepStatus.COMPLETED,
            output=normalized,
        )


class AnalysisStep(PipelineStep):
    """Analysis step."""
    
    def __init__(
        self,
        module,
        analysis_type: str,
        params: Optional[Dict] = None,
        data_step: str = "normalization",
    ):
        super().__init__(
            name=f"analysis_{analysis_type}",
            description=f"Run {analysis_type} analysis",
            dependencies=[data_step],
        )
        self.module = module
        self.analysis_type = analysis_type
        self.params = params or {}
        self.data_step = data_step
    
    async def execute(self, context: PipelineContext) -> StepResult:
        from backend.omics.base.omics_base import AnalysisParams
        
        data = context.get_result(self.data_step)
        params = AnalysisParams(
            analysis_type=self.analysis_type,
            parameters=self.params,
        )
        result = self.module.analyze(data, params)
        return StepResult(
            step_name=self.name,
            status=StepStatus.COMPLETED if result.status == "success" else StepStatus.FAILED,
            output=result,
            metrics=result.metrics,
        )

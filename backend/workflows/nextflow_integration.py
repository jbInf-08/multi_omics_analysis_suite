"""
Nextflow Integration Module
===========================

Run and manage Nextflow pipelines for bioinformatics workflows.
"""

import asyncio
import subprocess
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
import tempfile
import shutil


def utc_now() -> datetime:
    """Return current UTC time."""
    return datetime.now(timezone.utc)

logger = logging.getLogger(__name__)


class PipelineStatus(str, Enum):
    """Nextflow pipeline execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class NextflowConfig:
    """Configuration for Nextflow execution."""
    nextflow_path: str = "nextflow"
    work_dir: Optional[Path] = None
    output_dir: Optional[Path] = None
    config_file: Optional[Path] = None
    profile: Optional[str] = None
    resume: bool = False
    with_report: bool = True
    with_timeline: bool = True
    with_dag: bool = False
    max_memory: str = "8.GB"
    max_cpus: int = 4
    max_time: str = "24.h"


@dataclass
class PipelineResult:
    """Result from a Nextflow pipeline run."""
    pipeline: str
    status: PipelineStatus
    exit_code: int
    duration_seconds: float
    output_dir: Optional[Path]
    log_file: Optional[Path]
    report_file: Optional[Path]
    stdout: str
    stderr: str
    parameters: Dict[str, Any]
    started_at: datetime
    completed_at: datetime


class NextflowPipeline:
    """
    Represents a Nextflow pipeline.
    
    Can be a local file, GitHub repository, or nf-core pipeline.
    """
    
    def __init__(
        self,
        name: str,
        source: str,  # Path, GitHub URL, or nf-core pipeline name
        revision: Optional[str] = None,
        description: str = "",
    ):
        """
        Initialize Nextflow pipeline.
        
        Args:
            name: Pipeline name
            source: Pipeline source (path, URL, or nf-core name)
            revision: Git revision/branch/tag
            description: Pipeline description
        """
        self.name = name
        self.source = source
        self.revision = revision
        self.description = description
    
    @property
    def is_nfcore(self) -> bool:
        """Check if this is an nf-core pipeline."""
        return self.source.startswith("nf-core/")
    
    @property
    def is_local(self) -> bool:
        """Check if this is a local pipeline."""
        return Path(self.source).exists()


# Pre-defined nf-core pipelines
NFCORE_PIPELINES = {
    "rnaseq": NextflowPipeline(
        "nf-core/rnaseq",
        "nf-core/rnaseq",
        description="RNA sequencing analysis pipeline"
    ),
    "sarek": NextflowPipeline(
        "nf-core/sarek",
        "nf-core/sarek",
        description="Analysis pipeline for WGS/WES/targeted sequencing"
    ),
    "methylseq": NextflowPipeline(
        "nf-core/methylseq",
        "nf-core/methylseq",
        description="Methylation analysis pipeline"
    ),
    "atacseq": NextflowPipeline(
        "nf-core/atacseq",
        "nf-core/atacseq",
        description="ATAC-seq analysis pipeline"
    ),
    "chipseq": NextflowPipeline(
        "nf-core/chipseq",
        "nf-core/chipseq",
        description="ChIP-seq analysis pipeline"
    ),
    "scrnaseq": NextflowPipeline(
        "nf-core/scrnaseq",
        "nf-core/scrnaseq",
        description="Single-cell RNA-seq analysis pipeline"
    ),
}


class NextflowRunner:
    """
    Execute and manage Nextflow pipelines.
    
    Provides:
    - Pipeline execution with parameter management
    - Progress monitoring
    - Log capture
    - Resource management
    """
    
    def __init__(self, config: Optional[NextflowConfig] = None):
        """
        Initialize Nextflow runner.
        
        Args:
            config: Nextflow configuration
        """
        self.config = config or NextflowConfig()
        self._processes: Dict[str, subprocess.Popen] = {}
    
    def _check_nextflow(self) -> bool:
        """Check if Nextflow is installed."""
        try:
            result = subprocess.run(
                [self.config.nextflow_path, "-version"],
                capture_output=True,
                text=True,
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False
    
    async def run_pipeline(
        self,
        pipeline: NextflowPipeline,
        params: Dict[str, Any],
        run_name: Optional[str] = None,
        callback: Optional[callable] = None,
    ) -> PipelineResult:
        """
        Run a Nextflow pipeline.
        
        Args:
            pipeline: Pipeline to run
            params: Pipeline parameters
            run_name: Optional run name
            callback: Progress callback function
            
        Returns:
            PipelineResult
        """
        if not self._check_nextflow():
            raise RuntimeError("Nextflow is not installed or not in PATH")
        
        started_at = utc_now()
        run_name = run_name or f"{pipeline.name}_{started_at.strftime('%Y%m%d_%H%M%S')}"
        
        # Setup directories
        work_dir = self.config.work_dir or Path(tempfile.mkdtemp())
        output_dir = self.config.output_dir or work_dir / "results"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Build command
        cmd = [
            self.config.nextflow_path,
            "run",
            pipeline.source,
            "-name", run_name,
            "-work-dir", str(work_dir),
            "--outdir", str(output_dir),
        ]
        
        # Add revision
        if pipeline.revision:
            cmd.extend(["-r", pipeline.revision])
        
        # Add profile
        if self.config.profile:
            cmd.extend(["-profile", self.config.profile])
        
        # Add config file
        if self.config.config_file:
            cmd.extend(["-c", str(self.config.config_file)])
        
        # Add resume flag
        if self.config.resume:
            cmd.append("-resume")
        
        # Add reporting
        report_file = None
        if self.config.with_report:
            report_file = output_dir / f"{run_name}_report.html"
            cmd.extend(["-with-report", str(report_file)])
        
        if self.config.with_timeline:
            cmd.extend(["-with-timeline", str(output_dir / f"{run_name}_timeline.html")])
        
        if self.config.with_dag:
            cmd.extend(["-with-dag", str(output_dir / f"{run_name}_dag.svg")])
        
        # Add parameters
        for key, value in params.items():
            if isinstance(value, bool):
                if value:
                    cmd.append(f"--{key}")
            else:
                cmd.extend([f"--{key}", str(value)])
        
        # Run pipeline
        logger.info(f"Running Nextflow pipeline: {' '.join(cmd)}")
        
        log_file = output_dir / f"{run_name}.log"
        
        try:
            with open(log_file, "w") as log:
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=str(work_dir),
                )
                
                self._processes[run_name] = process
                
                stdout, stderr = await process.communicate()
                
                # Write to log
                log.write(stdout.decode())
                if stderr:
                    log.write("\n--- STDERR ---\n")
                    log.write(stderr.decode())
            
            completed_at = utc_now()
            duration = (completed_at - started_at).total_seconds()
            
            status = PipelineStatus.COMPLETED if process.returncode == 0 else PipelineStatus.FAILED
            
            return PipelineResult(
                pipeline=pipeline.name,
                status=status,
                exit_code=process.returncode,
                duration_seconds=duration,
                output_dir=output_dir,
                log_file=log_file,
                report_file=report_file,
                stdout=stdout.decode(),
                stderr=stderr.decode(),
                parameters=params,
                started_at=started_at,
                completed_at=completed_at,
            )
            
        except Exception as e:
            logger.error(f"Pipeline execution failed: {e}")
            return PipelineResult(
                pipeline=pipeline.name,
                status=PipelineStatus.FAILED,
                exit_code=-1,
                duration_seconds=0,
                output_dir=output_dir,
                log_file=log_file,
                report_file=None,
                stdout="",
                stderr=str(e),
                parameters=params,
                started_at=started_at,
                completed_at=utc_now(),
            )
        finally:
            if run_name in self._processes:
                del self._processes[run_name]
    
    async def run_rnaseq(
        self,
        input_dir: Path,
        genome: str = "GRCh38",
        aligner: str = "star_salmon",
        **kwargs
    ) -> PipelineResult:
        """
        Run nf-core/rnaseq pipeline.
        
        Args:
            input_dir: Input directory with FASTQ files
            genome: Reference genome
            aligner: Alignment tool
            **kwargs: Additional parameters
            
        Returns:
            PipelineResult
        """
        params = {
            "input": str(input_dir / "samplesheet.csv"),
            "genome": genome,
            "aligner": aligner,
            "max_memory": self.config.max_memory,
            "max_cpus": self.config.max_cpus,
            "max_time": self.config.max_time,
            **kwargs,
        }
        
        return await self.run_pipeline(NFCORE_PIPELINES["rnaseq"], params)
    
    async def run_sarek(
        self,
        input_dir: Path,
        genome: str = "GATK.GRCh38",
        tools: Optional[List[str]] = None,
        **kwargs
    ) -> PipelineResult:
        """
        Run nf-core/sarek pipeline for variant calling.
        
        Args:
            input_dir: Input directory
            genome: Reference genome
            tools: Analysis tools to run
            **kwargs: Additional parameters
            
        Returns:
            PipelineResult
        """
        params = {
            "input": str(input_dir / "samplesheet.csv"),
            "genome": genome,
            "tools": ",".join(tools) if tools else "strelka,mutect2",
            "max_memory": self.config.max_memory,
            "max_cpus": self.config.max_cpus,
            **kwargs,
        }
        
        return await self.run_pipeline(NFCORE_PIPELINES["sarek"], params)
    
    def cancel_pipeline(self, run_name: str) -> bool:
        """Cancel a running pipeline."""
        if run_name in self._processes:
            process = self._processes[run_name]
            process.terminate()
            return True
        return False
    
    def list_running(self) -> List[str]:
        """List running pipeline names."""
        return list(self._processes.keys())

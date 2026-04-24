"""
Snakemake Manager Module
========================

Run and manage Snakemake workflows for bioinformatics analysis.
"""

import asyncio
import subprocess
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
import tempfile
import yaml


def utc_now() -> datetime:
    """Return current UTC time."""
    return datetime.now(timezone.utc)

logger = logging.getLogger(__name__)


class WorkflowStatus(str, Enum):
    """Snakemake workflow execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class SnakemakeConfig:
    """Configuration for Snakemake execution."""
    snakemake_path: str = "snakemake"
    cores: int = 4
    use_conda: bool = True
    use_singularity: bool = False
    singularity_args: str = ""
    conda_frontend: str = "mamba"
    keep_going: bool = False
    dryrun: bool = False
    forceall: bool = False
    printshellcmds: bool = True
    latency_wait: int = 60
    rerun_incomplete: bool = True


@dataclass
class WorkflowResult:
    """Result from a Snakemake workflow run."""
    workflow_name: str
    status: WorkflowStatus
    exit_code: int
    duration_seconds: float
    output_dir: Optional[Path]
    log_file: Optional[Path]
    stdout: str
    stderr: str
    config: Dict[str, Any]
    started_at: datetime
    completed_at: datetime
    jobs_completed: int = 0
    jobs_failed: int = 0


class SnakemakeWorkflow:
    """
    Represents a Snakemake workflow.
    """
    
    def __init__(
        self,
        name: str,
        snakefile: Path,
        config_file: Optional[Path] = None,
        description: str = "",
    ):
        """
        Initialize Snakemake workflow.
        
        Args:
            name: Workflow name
            snakefile: Path to Snakefile
            config_file: Path to config file
            description: Workflow description
        """
        self.name = name
        self.snakefile = Path(snakefile)
        self.config_file = Path(config_file) if config_file else None
        self.description = description
    
    def validate(self) -> bool:
        """Validate workflow files exist."""
        if not self.snakefile.exists():
            return False
        if self.config_file and not self.config_file.exists():
            return False
        return True


class SnakemakeRunner:
    """
    Execute and manage Snakemake workflows.
    
    Provides:
    - Workflow execution with parameter management
    - Conda/Singularity environment support
    - Progress monitoring
    - Resource management
    """
    
    def __init__(self, config: Optional[SnakemakeConfig] = None):
        """
        Initialize Snakemake runner.
        
        Args:
            config: Snakemake configuration
        """
        self.config = config or SnakemakeConfig()
        self._processes: Dict[str, subprocess.Popen] = {}
    
    def _check_snakemake(self) -> bool:
        """Check if Snakemake is installed."""
        try:
            result = subprocess.run(
                [self.config.snakemake_path, "--version"],
                capture_output=True,
                text=True,
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False
    
    async def run_workflow(
        self,
        workflow: SnakemakeWorkflow,
        config_overrides: Optional[Dict[str, Any]] = None,
        targets: Optional[List[str]] = None,
        working_dir: Optional[Path] = None,
        run_name: Optional[str] = None,
    ) -> WorkflowResult:
        """
        Run a Snakemake workflow.
        
        Args:
            workflow: Workflow to run
            config_overrides: Configuration overrides
            targets: Target rules to run
            working_dir: Working directory
            run_name: Run identifier
            
        Returns:
            WorkflowResult
        """
        if not self._check_snakemake():
            raise RuntimeError("Snakemake is not installed or not in PATH")
        
        if not workflow.validate():
            raise ValueError(f"Invalid workflow: {workflow.name}")
        
        started_at = utc_now()
        run_name = run_name or f"{workflow.name}_{started_at.strftime('%Y%m%d_%H%M%S')}"
        
        # Setup working directory
        work_dir = working_dir or Path(tempfile.mkdtemp())
        work_dir.mkdir(parents=True, exist_ok=True)
        
        # Build command
        cmd = [
            self.config.snakemake_path,
            "--snakefile", str(workflow.snakefile),
            "--cores", str(self.config.cores),
            "--latency-wait", str(self.config.latency_wait),
        ]
        
        # Add config file
        if workflow.config_file:
            cmd.extend(["--configfile", str(workflow.config_file)])
        
        # Add config overrides
        if config_overrides:
            for key, value in config_overrides.items():
                cmd.extend(["--config", f"{key}={value}"])
        
        # Add targets
        if targets:
            cmd.extend(targets)
        
        # Add execution options
        if self.config.use_conda:
            cmd.append("--use-conda")
            cmd.extend(["--conda-frontend", self.config.conda_frontend])
        
        if self.config.use_singularity:
            cmd.append("--use-singularity")
            if self.config.singularity_args:
                cmd.extend(["--singularity-args", self.config.singularity_args])
        
        if self.config.keep_going:
            cmd.append("--keep-going")
        
        if self.config.dryrun:
            cmd.append("--dryrun")
        
        if self.config.forceall:
            cmd.append("--forceall")
        
        if self.config.printshellcmds:
            cmd.append("--printshellcmds")
        
        if self.config.rerun_incomplete:
            cmd.append("--rerun-incomplete")
        
        # Run workflow
        logger.info(f"Running Snakemake workflow: {' '.join(cmd)}")
        
        log_file = work_dir / f"{run_name}.log"
        
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
                
                log.write(stdout.decode())
                if stderr:
                    log.write("\n--- STDERR ---\n")
                    log.write(stderr.decode())
            
            completed_at = utc_now()
            duration = (completed_at - started_at).total_seconds()
            
            status = WorkflowStatus.COMPLETED if process.returncode == 0 else WorkflowStatus.FAILED
            
            return WorkflowResult(
                workflow_name=workflow.name,
                status=status,
                exit_code=process.returncode,
                duration_seconds=duration,
                output_dir=work_dir,
                log_file=log_file,
                stdout=stdout.decode(),
                stderr=stderr.decode(),
                config=config_overrides or {},
                started_at=started_at,
                completed_at=completed_at,
            )
            
        except Exception as e:
            logger.error(f"Workflow execution failed: {e}")
            return WorkflowResult(
                workflow_name=workflow.name,
                status=WorkflowStatus.FAILED,
                exit_code=-1,
                duration_seconds=0,
                output_dir=work_dir,
                log_file=log_file,
                stdout="",
                stderr=str(e),
                config=config_overrides or {},
                started_at=started_at,
                completed_at=utc_now(),
            )
        finally:
            if run_name in self._processes:
                del self._processes[run_name]
    
    async def dry_run(
        self,
        workflow: SnakemakeWorkflow,
        config_overrides: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Perform a dry run to see what would be executed.
        
        Args:
            workflow: Workflow to check
            config_overrides: Configuration overrides
            
        Returns:
            Dry run output
        """
        original_dryrun = self.config.dryrun
        self.config.dryrun = True
        
        try:
            result = await self.run_workflow(workflow, config_overrides)
            return result.stdout
        finally:
            self.config.dryrun = original_dryrun
    
    def create_workflow_from_template(
        self,
        name: str,
        template: str,
        output_dir: Path,
        config: Dict[str, Any],
    ) -> SnakemakeWorkflow:
        """
        Create a workflow from a template.
        
        Args:
            name: Workflow name
            template: Template name
            output_dir: Output directory
            config: Workflow configuration
            
        Returns:
            SnakemakeWorkflow
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        
        templates = {
            "rnaseq": self._rnaseq_template(),
            "variant_calling": self._variant_calling_template(),
            "differential_expression": self._de_template(),
        }
        
        snakefile_content = templates.get(template, templates["rnaseq"])
        snakefile = output_dir / "Snakefile"
        snakefile.write_text(snakefile_content)
        
        config_file = output_dir / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config, f)
        
        return SnakemakeWorkflow(name, snakefile, config_file)
    
    def _rnaseq_template(self) -> str:
        """Generate RNA-seq workflow template."""
        return '''
configfile: "config.yaml"

SAMPLES = config["samples"]

rule all:
    input:
        expand("results/counts/{sample}.counts", sample=SAMPLES),
        "results/multiqc_report.html"

rule fastqc:
    input:
        r1="data/{sample}_R1.fastq.gz",
        r2="data/{sample}_R2.fastq.gz"
    output:
        html="results/fastqc/{sample}_fastqc.html",
        zip="results/fastqc/{sample}_fastqc.zip"
    conda:
        "envs/qc.yaml"
    shell:
        "fastqc {input.r1} {input.r2} -o results/fastqc/"

rule align:
    input:
        r1="data/{sample}_R1.fastq.gz",
        r2="data/{sample}_R2.fastq.gz",
        index=config["genome_index"]
    output:
        bam="results/aligned/{sample}.bam"
    conda:
        "envs/align.yaml"
    threads: 8
    shell:
        "STAR --runThreadN {threads} --genomeDir {input.index} "
        "--readFilesIn {input.r1} {input.r2} --readFilesCommand zcat "
        "--outFileNamePrefix results/aligned/{wildcards.sample}_ "
        "--outSAMtype BAM SortedByCoordinate && "
        "mv results/aligned/{wildcards.sample}_Aligned.sortedByCoord.out.bam {output.bam}"

rule count:
    input:
        bam="results/aligned/{sample}.bam",
        gtf=config["annotation"]
    output:
        counts="results/counts/{sample}.counts"
    conda:
        "envs/count.yaml"
    shell:
        "featureCounts -T 4 -a {input.gtf} -o {output.counts} {input.bam}"

rule multiqc:
    input:
        expand("results/fastqc/{sample}_fastqc.html", sample=SAMPLES),
        expand("results/counts/{sample}.counts", sample=SAMPLES)
    output:
        "results/multiqc_report.html"
    conda:
        "envs/qc.yaml"
    shell:
        "multiqc results/ -o results/"
'''
    
    def _variant_calling_template(self) -> str:
        """Generate variant calling workflow template."""
        return '''
configfile: "config.yaml"

SAMPLES = config["samples"]

rule all:
    input:
        "results/variants/merged.vcf.gz"

rule align:
    input:
        r1="data/{sample}_R1.fastq.gz",
        r2="data/{sample}_R2.fastq.gz",
        ref=config["reference"]
    output:
        bam="results/aligned/{sample}.bam",
        bai="results/aligned/{sample}.bam.bai"
    conda:
        "envs/align.yaml"
    threads: 8
    shell:
        "bwa mem -t {threads} {input.ref} {input.r1} {input.r2} | "
        "samtools sort -@ {threads} -o {output.bam} && "
        "samtools index {output.bam}"

rule call_variants:
    input:
        bam="results/aligned/{sample}.bam",
        ref=config["reference"]
    output:
        vcf="results/variants/{sample}.vcf.gz"
    conda:
        "envs/variant.yaml"
    shell:
        "bcftools mpileup -Ou -f {input.ref} {input.bam} | "
        "bcftools call -mv -Oz -o {output.vcf} && "
        "bcftools index {output.vcf}"

rule merge_vcfs:
    input:
        vcfs=expand("results/variants/{sample}.vcf.gz", sample=SAMPLES)
    output:
        "results/variants/merged.vcf.gz"
    conda:
        "envs/variant.yaml"
    shell:
        "bcftools merge {input.vcfs} -Oz -o {output}"
'''
    
    def _de_template(self) -> str:
        """Generate differential expression workflow template."""
        return '''
configfile: "config.yaml"

rule all:
    input:
        "results/de/differential_expression.csv",
        "results/de/volcano_plot.png"

rule run_deseq2:
    input:
        counts=config["counts_matrix"],
        metadata=config["metadata"]
    output:
        results="results/de/differential_expression.csv"
    conda:
        "envs/deseq2.yaml"
    script:
        "scripts/run_deseq2.R"

rule plot_volcano:
    input:
        de_results="results/de/differential_expression.csv"
    output:
        plot="results/de/volcano_plot.png"
    conda:
        "envs/plotting.yaml"
    script:
        "scripts/volcano_plot.py"
'''
    
    def cancel_workflow(self, run_name: str) -> bool:
        """Cancel a running workflow."""
        if run_name in self._processes:
            process = self._processes[run_name]
            process.terminate()
            return True
        return False
    
    def list_running(self) -> List[str]:
        """List running workflow names."""
        return list(self._processes.keys())

"""
Data Validation & Schema Versioning
====================================

Input file format validation, analysis parameter schema versioning,
and result provenance tracking.
"""

import re
import gzip
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json

from pydantic import BaseModel, Field, validator


# =============================================================================
# File Format Validators
# =============================================================================

class FileFormat(str, Enum):
    """Supported file formats."""
    FASTA = "fasta"
    FASTQ = "fastq"
    VCF = "vcf"
    BED = "bed"
    GFF = "gff"
    GTF = "gtf"
    SAM = "sam"
    BAM = "bam"
    CSV = "csv"
    TSV = "tsv"
    H5AD = "h5ad"
    LOOM = "loom"
    MTX = "mtx"
    UNKNOWN = "unknown"


@dataclass
class ValidationResult:
    """Result of file validation."""
    is_valid: bool
    format: FileFormat
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class FileValidator:
    """Validates various bioinformatics file formats."""
    
    # File signatures (magic bytes)
    SIGNATURES = {
        b'\x1f\x8b': 'gzip',
        b'BAM\x01': 'bam',
        b'BCF\x02': 'bcf',
    }
    
    @classmethod
    def detect_format(cls, filepath: Union[str, Path]) -> FileFormat:
        """Detect file format from content and extension."""
        filepath = Path(filepath)
        
        # Check extension first
        ext = filepath.suffix.lower()
        if ext == '.gz':
            ext = Path(filepath.stem).suffix.lower()
        
        extension_map = {
            '.fasta': FileFormat.FASTA, '.fa': FileFormat.FASTA, '.fna': FileFormat.FASTA,
            '.fastq': FileFormat.FASTQ, '.fq': FileFormat.FASTQ,
            '.vcf': FileFormat.VCF,
            '.bed': FileFormat.BED,
            '.gff': FileFormat.GFF, '.gff3': FileFormat.GFF,
            '.gtf': FileFormat.GTF,
            '.sam': FileFormat.SAM,
            '.bam': FileFormat.BAM,
            '.csv': FileFormat.CSV,
            '.tsv': FileFormat.TSV, '.txt': FileFormat.TSV,
            '.h5ad': FileFormat.H5AD,
            '.loom': FileFormat.LOOM,
            '.mtx': FileFormat.MTX,
        }
        
        return extension_map.get(ext, FileFormat.UNKNOWN)
    
    @classmethod
    def validate_file(cls, filepath: Union[str, Path]) -> ValidationResult:
        """Validate a file based on its format."""
        filepath = Path(filepath)
        
        if not filepath.exists():
            return ValidationResult(
                is_valid=False,
                format=FileFormat.UNKNOWN,
                errors=[f"File not found: {filepath}"]
            )
        
        file_format = cls.detect_format(filepath)
        
        validators = {
            FileFormat.FASTA: cls._validate_fasta,
            FileFormat.FASTQ: cls._validate_fastq,
            FileFormat.VCF: cls._validate_vcf,
            FileFormat.BED: cls._validate_bed,
            FileFormat.CSV: cls._validate_csv,
            FileFormat.TSV: cls._validate_tsv,
        }
        
        validator_func = validators.get(file_format)
        if validator_func:
            return validator_func(filepath)
        
        return ValidationResult(
            is_valid=True,
            format=file_format,
            warnings=[f"No specific validation for format: {file_format}"]
        )
    
    @classmethod
    def _open_file(cls, filepath: Path):
        """Open file, handling gzip compression."""
        if filepath.suffix.lower() == '.gz':
            return gzip.open(filepath, 'rt')
        return open(filepath, 'r')
    
    @classmethod
    def _validate_fasta(cls, filepath: Path) -> ValidationResult:
        """Validate FASTA format."""
        errors = []
        warnings = []
        metadata = {"sequences": 0, "total_length": 0}
        
        try:
            with cls._open_file(filepath) as f:
                line_num = 0
                in_sequence = False
                current_seq_len = 0
                
                for line in f:
                    line_num += 1
                    line = line.strip()
                    
                    if not line:
                        continue
                    
                    if line.startswith('>'):
                        if in_sequence and current_seq_len == 0:
                            warnings.append(f"Empty sequence at line {line_num}")
                        metadata["sequences"] += 1
                        in_sequence = True
                        current_seq_len = 0
                    elif in_sequence:
                        # Validate sequence characters
                        valid_chars = set('ACGTNacgtn-.')
                        invalid = set(line) - valid_chars
                        if invalid:
                            errors.append(f"Invalid characters at line {line_num}: {invalid}")
                        current_seq_len += len(line)
                        metadata["total_length"] += len(line)
                    else:
                        errors.append(f"Sequence without header at line {line_num}")
                    
                    # Only check first 1000 lines for performance
                    if line_num > 1000:
                        break
                        
        except Exception as e:
            errors.append(f"Error reading file: {str(e)}")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            format=FileFormat.FASTA,
            errors=errors,
            warnings=warnings,
            metadata=metadata
        )
    
    @classmethod
    def _validate_fastq(cls, filepath: Path) -> ValidationResult:
        """Validate FASTQ format."""
        errors = []
        warnings = []
        metadata = {"reads": 0, "avg_quality": 0}
        
        try:
            with cls._open_file(filepath) as f:
                line_num = 0
                record_num = 0
                
                while True:
                    # Read 4 lines at a time
                    header = f.readline()
                    if not header:
                        break
                    
                    sequence = f.readline()
                    plus = f.readline()
                    quality = f.readline()
                    
                    line_num += 4
                    record_num += 1
                    
                    # Validate header
                    if not header.strip().startswith('@'):
                        errors.append(f"Invalid header at record {record_num}")
                    
                    # Validate plus line
                    if not plus.strip().startswith('+'):
                        errors.append(f"Invalid plus line at record {record_num}")
                    
                    # Validate sequence/quality length match
                    if len(sequence.strip()) != len(quality.strip()):
                        errors.append(f"Sequence/quality length mismatch at record {record_num}")
                    
                    metadata["reads"] = record_num
                    
                    # Only check first 1000 records
                    if record_num > 1000:
                        break
                        
        except Exception as e:
            errors.append(f"Error reading file: {str(e)}")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            format=FileFormat.FASTQ,
            errors=errors,
            warnings=warnings,
            metadata=metadata
        )
    
    @classmethod
    def _validate_vcf(cls, filepath: Path) -> ValidationResult:
        """Validate VCF format."""
        errors = []
        warnings = []
        metadata = {"variants": 0, "samples": 0}
        
        try:
            with cls._open_file(filepath) as f:
                has_header = False
                has_format_version = False
                
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    
                    if line.startswith('##'):
                        if line.startswith('##fileformat='):
                            has_format_version = True
                    elif line.startswith('#CHROM'):
                        has_header = True
                        parts = line.split('\t')
                        if len(parts) >= 9:
                            metadata["samples"] = len(parts) - 9
                    elif line and not line.startswith('#'):
                        metadata["variants"] += 1
                        parts = line.split('\t')
                        if len(parts) < 8:
                            errors.append(f"Invalid VCF line at {line_num}: too few columns")
                    
                    if line_num > 1000:
                        break
                
                if not has_format_version:
                    warnings.append("Missing fileformat header")
                if not has_header:
                    errors.append("Missing #CHROM header line")
                    
        except Exception as e:
            errors.append(f"Error reading file: {str(e)}")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            format=FileFormat.VCF,
            errors=errors,
            warnings=warnings,
            metadata=metadata
        )
    
    @classmethod
    def _validate_bed(cls, filepath: Path) -> ValidationResult:
        """Validate BED format."""
        errors = []
        warnings = []
        metadata = {"regions": 0}
        
        try:
            with cls._open_file(filepath) as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line or line.startswith('#') or line.startswith('track') or line.startswith('browser'):
                        continue
                    
                    parts = line.split('\t')
                    if len(parts) < 3:
                        errors.append(f"Line {line_num}: BED requires at least 3 columns")
                        continue
                    
                    # Validate coordinates
                    try:
                        start = int(parts[1])
                        end = int(parts[2])
                        if start < 0 or end < 0:
                            errors.append(f"Line {line_num}: Negative coordinates")
                        if start > end:
                            errors.append(f"Line {line_num}: Start > End")
                    except ValueError:
                        errors.append(f"Line {line_num}: Invalid coordinates")
                    
                    metadata["regions"] += 1
                    
                    if line_num > 1000:
                        break
                        
        except Exception as e:
            errors.append(f"Error reading file: {str(e)}")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            format=FileFormat.BED,
            errors=errors,
            warnings=warnings,
            metadata=metadata
        )
    
    @classmethod
    def _validate_csv(cls, filepath: Path) -> ValidationResult:
        """Validate CSV format."""
        return cls._validate_delimited(filepath, ',', FileFormat.CSV)
    
    @classmethod
    def _validate_tsv(cls, filepath: Path) -> ValidationResult:
        """Validate TSV format."""
        return cls._validate_delimited(filepath, '\t', FileFormat.TSV)
    
    @classmethod
    def _validate_delimited(cls, filepath: Path, delimiter: str, fmt: FileFormat) -> ValidationResult:
        """Validate delimited file format."""
        errors = []
        warnings = []
        metadata = {"rows": 0, "columns": 0}
        
        try:
            with cls._open_file(filepath) as f:
                header = f.readline()
                if header:
                    columns = len(header.strip().split(delimiter))
                    metadata["columns"] = columns
                
                for line_num, line in enumerate(f, 2):
                    if not line.strip():
                        continue
                    
                    cols = len(line.strip().split(delimiter))
                    if cols != columns:
                        warnings.append(f"Line {line_num}: Column count mismatch ({cols} vs {columns})")
                    
                    metadata["rows"] += 1
                    
                    if line_num > 1000:
                        break
                        
        except Exception as e:
            errors.append(f"Error reading file: {str(e)}")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            format=fmt,
            errors=errors,
            warnings=warnings,
            metadata=metadata
        )


# =============================================================================
# Analysis Parameter Schema Versioning
# =============================================================================

class ParameterSchema(BaseModel):
    """Base schema for analysis parameters."""
    version: str = Field(default="1.0.0", description="Schema version")
    
    class Config:
        extra = "allow"


class DifferentialExpressionParams(ParameterSchema):
    """Parameters for differential expression analysis."""
    method: str = Field(default="deseq2", description="DE method (deseq2, edger, limma)")
    fdr_threshold: float = Field(default=0.05, ge=0, le=1, description="FDR threshold")
    log2fc_threshold: float = Field(default=1.0, ge=0, description="Log2 fold change threshold")
    min_counts: int = Field(default=10, ge=0, description="Minimum count filter")
    normalize: bool = Field(default=True, description="Apply normalization")
    
    @validator('method')
    def validate_method(cls, v):
        allowed = ['deseq2', 'edger', 'limma', 'ttest', 'wilcoxon']
        if v not in allowed:
            raise ValueError(f"Method must be one of {allowed}")
        return v


class PathwayAnalysisParams(ParameterSchema):
    """Parameters for pathway analysis."""
    database: str = Field(default="kegg", description="Pathway database")
    method: str = Field(default="gsea", description="Enrichment method (gsea, ora)")
    organism: str = Field(default="human", description="Organism")
    min_size: int = Field(default=10, ge=1, description="Minimum gene set size")
    max_size: int = Field(default=500, ge=1, description="Maximum gene set size")
    pvalue_threshold: float = Field(default=0.05, ge=0, le=1)


class ClusteringParams(ParameterSchema):
    """Parameters for clustering analysis."""
    method: str = Field(default="leiden", description="Clustering method")
    n_clusters: Optional[int] = Field(default=None, ge=2, description="Number of clusters")
    resolution: float = Field(default=1.0, gt=0, description="Resolution parameter")
    n_neighbors: int = Field(default=15, ge=2, description="Number of neighbors")
    n_pcs: int = Field(default=50, ge=2, description="Number of PCs")


# Schema registry
PARAMETER_SCHEMAS = {
    "differential_expression": DifferentialExpressionParams,
    "pathway_analysis": PathwayAnalysisParams,
    "clustering": ClusteringParams,
}


def validate_parameters(analysis_type: str, params: Dict[str, Any]) -> Tuple[bool, Dict[str, Any], List[str]]:
    """Validate analysis parameters against schema."""
    schema_class = PARAMETER_SCHEMAS.get(analysis_type)
    
    if not schema_class:
        return True, params, [f"No schema defined for {analysis_type}"]
    
    try:
        validated = schema_class(**params)
        return True, validated.dict(), []
    except Exception as e:
        return False, params, [str(e)]


# =============================================================================
# Result Provenance Tracking
# =============================================================================

@dataclass
class Provenance:
    """Tracks the provenance of analysis results."""
    id: str
    created_at: datetime
    analysis_id: str
    analysis_type: str
    parameters: Dict[str, Any]
    input_files: List[Dict[str, str]]  # {path, checksum, format}
    software_versions: Dict[str, str]
    environment: Dict[str, str]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat(),
            "analysis_id": self.analysis_id,
            "analysis_type": self.analysis_type,
            "parameters": self.parameters,
            "input_files": self.input_files,
            "software_versions": self.software_versions,
            "environment": self.environment,
        }
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)


def compute_file_checksum(filepath: Union[str, Path], algorithm: str = "sha256") -> str:
    """Compute file checksum."""
    filepath = Path(filepath)
    hasher = hashlib.new(algorithm)
    
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            hasher.update(chunk)
    
    return hasher.hexdigest()


def create_provenance(
    analysis_id: str,
    analysis_type: str,
    parameters: Dict[str, Any],
    input_files: List[str],
) -> Provenance:
    """Create a provenance record for an analysis."""
    import platform
    import uuid
    import sys
    
    # Compute checksums for input files
    file_info = []
    for filepath in input_files:
        path = Path(filepath)
        if path.exists():
            file_info.append({
                "path": str(path),
                "checksum": compute_file_checksum(path),
                "format": FileValidator.detect_format(path).value,
                "size": path.stat().st_size,
            })
    
    # Collect software versions
    software_versions = {
        "python": sys.version,
        "platform": platform.platform(),
    }
    
    # Try to get package versions
    try:
        import numpy
        software_versions["numpy"] = numpy.__version__
    except ImportError:
        pass
    
    try:
        import pandas
        software_versions["pandas"] = pandas.__version__
    except ImportError:
        pass
    
    try:
        import scipy
        software_versions["scipy"] = scipy.__version__
    except ImportError:
        pass
    
    return Provenance(
        id=str(uuid.uuid4()),
        created_at=datetime.utcnow(),
        analysis_id=analysis_id,
        analysis_type=analysis_type,
        parameters=parameters,
        input_files=file_info,
        software_versions=software_versions,
        environment={
            "hostname": platform.node(),
            "processor": platform.processor(),
        }
    )

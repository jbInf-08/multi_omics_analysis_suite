"""Base Omics Module.
=================

Abstract base class and data types for all omics modules.
Every omics module (Genomics, Proteomics, etc.) must inherit from OmicsModuleBase.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import (
    Any,
)

import pandas as pd


def utc_now() -> datetime:
    """Return current UTC time."""
    return datetime.now(timezone.utc)


class OmicsCategory(str, Enum):
    """Omics category enumeration."""

    # Core Omics
    CORE = "core"

    # Modification Omics
    MODIFICATIONS = "modifications"

    # Interaction Omics
    INTERACTIONS = "interactions"

    # Clinical/Applied Omics
    CLINICAL = "clinical"

    # Specialized Omics
    SPECIALIZED = "specialized"

    @property
    def description(self) -> str:
        """Get category description."""
        descriptions = {
            "core": "Core omics types including genomics, proteomics, transcriptomics, and metabolomics",
            "modifications": "Post-translational and chemical modification omics",
            "interactions": "Molecular interaction and network omics",
            "clinical": "Clinical and applied omics for medical applications",
            "specialized": "Specialized and emerging omics disciplines",
        }
        return descriptions.get(self.value, "")


@dataclass
class DataSource:
    """Data source definition."""

    source_type: str  # file, database, api, s3
    path: str | None = None
    connection_string: str | None = None
    api_endpoint: str | None = None
    credentials: dict[str, str] | None = None
    format: str | None = None  # csv, tsv, vcf, etc.
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class OmicsData:
    """Container for omics data.

    Attributes:
        data: Main data matrix (samples x features)
        feature_names: Names/IDs of features (genes, proteins, etc.)
        sample_names: Names/IDs of samples
        feature_metadata: Additional metadata for features
        sample_metadata: Additional metadata for samples (clinical data, etc.)
        data_type: Type of omics data
        source: Original data source information

    """

    data: pd.DataFrame
    feature_names: list[str]
    sample_names: list[str]
    data_type: str
    feature_metadata: pd.DataFrame | None = None
    sample_metadata: pd.DataFrame | None = None
    source: DataSource | None = None
    preprocessing_history: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=utc_now)

    @property
    def n_samples(self) -> int:
        """Number of samples."""
        return len(self.sample_names)

    @property
    def n_features(self) -> int:
        """Number of features."""
        return len(self.feature_names)

    @property
    def shape(self) -> tuple:
        """Data shape (samples, features)."""
        return (self.n_samples, self.n_features)

    def copy(self) -> "OmicsData":
        """Create a deep copy."""
        return OmicsData(
            data=self.data.copy(),
            feature_names=self.feature_names.copy(),
            sample_names=self.sample_names.copy(),
            data_type=self.data_type,
            feature_metadata=(
                self.feature_metadata.copy() if self.feature_metadata is not None else None
            ),
            sample_metadata=(
                self.sample_metadata.copy() if self.sample_metadata is not None else None
            ),
            source=self.source,
            preprocessing_history=self.preprocessing_history.copy(),
            created_at=self.created_at,
        )


@dataclass
class QCMetric:
    """Quality control metric."""

    name: str
    value: float
    threshold: float | None = None
    passed: bool | None = None
    description: str | None = None

    def __post_init__(self):
        if self.threshold is not None and self.passed is None:
            self.passed = self.value >= self.threshold


@dataclass
class QCReport:
    """Quality control report."""

    passed: bool
    metrics: list[QCMetric]
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=utc_now)
    details: dict[str, Any] = field(default_factory=dict)

    def add_metric(self, metric: QCMetric):
        """Add a QC metric."""
        self.metrics.append(metric)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "passed": self.passed,
            "metrics": [
                {
                    "name": m.name,
                    "value": m.value,
                    "threshold": m.threshold,
                    "passed": m.passed,
                    "description": m.description,
                }
                for m in self.metrics
            ],
            "issues": self.issues,
            "warnings": self.warnings,
            "recommendations": self.recommendations,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details,
        }


@dataclass
class AnalysisParams:
    """Analysis parameters."""

    analysis_type: str
    parameters: dict[str, Any] = field(default_factory=dict)
    options: dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        """Get parameter value."""
        return self.parameters.get(key, default)

    def set(self, key: str, value: Any):
        """Set parameter value."""
        self.parameters[key] = value


@dataclass
class Visualization:
    """Visualization output."""

    name: str
    plot_type: str  # scatter, heatmap, volcano, network, etc.
    data: dict[str, Any]
    config: dict[str, Any] = field(default_factory=dict)
    title: str | None = None
    description: str | None = None

    def to_plotly(self) -> dict[str, Any]:
        """Convert to Plotly figure data."""
        return {
            "data": self.data,
            "layout": {
                "title": self.title,
                **self.config,
            },
        }


@dataclass
class AnalysisResult:
    """Analysis result container."""

    analysis_type: str
    status: str  # success, partial, failed
    data: dict[str, Any]
    summary: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, float] = field(default_factory=dict)
    visualizations: list[Visualization] = field(default_factory=list)
    tables: dict[str, pd.DataFrame] = field(default_factory=dict)
    files: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=utc_now)
    execution_time: float | None = None

    def add_visualization(self, viz: Visualization):
        """Add a visualization."""
        self.visualizations.append(viz)

    def add_table(self, name: str, df: pd.DataFrame):
        """Add a result table."""
        self.tables[name] = df

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary (excluding DataFrames)."""
        return {
            "analysis_type": self.analysis_type,
            "status": self.status,
            "data": self.data,
            "summary": self.summary,
            "metrics": self.metrics,
            "visualizations": [
                {"name": v.name, "type": v.plot_type, "title": v.title} for v in self.visualizations
            ],
            "tables": list(self.tables.keys()),
            "files": self.files,
            "warnings": self.warnings,
            "errors": self.errors,
            "timestamp": self.timestamp.isoformat(),
            "execution_time": self.execution_time,
        }


@dataclass
class Pipeline:
    """Pipeline definition."""

    name: str
    description: str
    steps: list[str]
    default_parameters: dict[str, Any] = field(default_factory=dict)
    required_inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    version: str = "1.0.0"


@dataclass
class AnalysisDefinition:
    """Analysis type definition."""

    name: str
    description: str
    parameters: dict[str, dict[str, Any]] = field(default_factory=dict)
    output_types: list[str] = field(default_factory=list)
    required_data: list[str] = field(default_factory=list)


class OmicsModuleBase(ABC):
    """Abstract base class for all omics modules.

    Every omics module must implement:
    - name: Module name
    - category: Module category (core, modifications, interactions, clinical, specialized)
    - load_data: Load data from a source
    - preprocess: Preprocess the data
    - quality_control: Run QC checks
    - normalize: Normalize the data
    - analyze: Run analysis
    - visualize: Generate visualizations
    - get_available_pipelines: List available pipelines
    - get_available_analyses: List available analyses
    """

    def __init__(self):
        self._is_active = True
        self._version = "1.0.0"
        self._supported_formats = []
        self._pipelines = []
        self._analyses = []

    @property
    @abstractmethod
    def name(self) -> str:
        """Module name (e.g., 'genomics', 'proteomics')."""
        pass

    @property
    @abstractmethod
    def category(self) -> OmicsCategory:
        """Module category."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Module description."""
        pass

    @property
    def version(self) -> str:
        """Module version."""
        return self._version

    @property
    def is_active(self) -> bool:
        """Whether module is active."""
        return self._is_active

    @property
    def supported_formats(self) -> list[str]:
        """Supported data formats."""
        return self._supported_formats

    @abstractmethod
    def load_data(self, source: DataSource) -> OmicsData:
        """Load data from a source.

        Args:
            source: Data source definition

        Returns:
            OmicsData object containing the loaded data

        """
        pass

    @abstractmethod
    def preprocess(
        self,
        data: OmicsData,
        params: dict[str, Any] | None = None,
    ) -> OmicsData:
        """Preprocess the data.

        Args:
            data: Input data
            params: Preprocessing parameters

        Returns:
            Preprocessed data

        """
        pass

    @abstractmethod
    def quality_control(
        self,
        data: OmicsData,
        params: dict[str, Any] | None = None,
    ) -> QCReport:
        """Run quality control checks.

        Args:
            data: Input data
            params: QC parameters

        Returns:
            QC report

        """
        pass

    @abstractmethod
    def normalize(
        self,
        data: OmicsData,
        method: str = "quantile",
        params: dict[str, Any] | None = None,
    ) -> OmicsData:
        """Normalize the data.

        Args:
            data: Input data
            method: Normalization method
            params: Normalization parameters

        Returns:
            Normalized data

        """
        pass

    @abstractmethod
    def analyze(
        self,
        data: OmicsData,
        params: AnalysisParams,
    ) -> AnalysisResult:
        """Run analysis.

        Args:
            data: Input data
            params: Analysis parameters

        Returns:
            Analysis result

        """
        pass

    @abstractmethod
    def visualize(
        self,
        result: AnalysisResult,
        plot_types: list[str] | None = None,
    ) -> list[Visualization]:
        """Generate visualizations.

        Args:
            result: Analysis result
            plot_types: Types of plots to generate

        Returns:
            List of visualizations

        """
        pass

    @abstractmethod
    def get_available_pipelines(self) -> list[Pipeline]:
        """Get list of available pipelines."""
        pass

    @abstractmethod
    def get_available_analyses(self) -> list[AnalysisDefinition]:
        """Get list of available analysis types."""
        pass

    def validate_data(self, data: OmicsData) -> bool:
        """Validate data for this omics type.

        Args:
            data: Data to validate

        Returns:
            True if valid

        """
        if data.data is None or data.data.empty:
            return False
        if len(data.feature_names) != data.data.shape[1]:
            return False
        return len(data.sample_names) == data.data.shape[0]

    def get_default_parameters(self, analysis_type: str) -> dict[str, Any]:
        """Get default parameters for an analysis type."""
        for analysis in self.get_available_analyses():
            if analysis.name == analysis_type:
                return {name: info.get("default") for name, info in analysis.parameters.items()}
        return {}

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(name={self.name}, category={self.category.value})>"

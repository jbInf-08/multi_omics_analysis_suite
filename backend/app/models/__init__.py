"""SQLAlchemy ORM models.

Importing this package registers every model with ``Base.metadata`` so that
``Base.metadata.create_all`` (see :func:`backend.app.core.database.init_db`)
picks up all tables.
"""

from backend.app.models.analysis import (
    Analysis,
    AnalysisResult,
    AnalysisStatus,
    AnalysisType,
    utc_now,
)
from backend.app.models.dataset import Dataset, DatasetStatus, OmicsType
from backend.app.models.pipeline import Pipeline, PipelineRun, PipelineStatus
from backend.app.models.project import Project, ProjectStatus
from backend.app.models.user import User

__all__ = [
    "Analysis",
    "AnalysisResult",
    "AnalysisStatus",
    "AnalysisType",
    "Dataset",
    "DatasetStatus",
    "OmicsType",
    "Pipeline",
    "PipelineRun",
    "PipelineStatus",
    "Project",
    "ProjectStatus",
    "User",
    "utc_now",
]

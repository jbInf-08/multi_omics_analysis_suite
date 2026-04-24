"""Analysis Schemas."""

from datetime import datetime, timezone
from uuid import UUID

from pydantic import Field

from backend.app.schemas.common import BaseSchema


class AnalysisBase(BaseSchema):
    """Base analysis schema."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    analysis_type: str
    omics_types: list[str] = Field(default_factory=list)


class AnalysisCreate(AnalysisBase):
    """Analysis creation schema."""

    project_id: UUID
    parameters: dict = Field(default_factory=dict)
    input_datasets: list[UUID] = Field(default_factory=list)


class AnalysisUpdate(BaseSchema):
    """Analysis update schema."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    parameters: dict | None = None
    status: str | None = None


class AnalysisResponse(AnalysisBase):
    """Analysis response schema."""

    id: UUID
    project_id: UUID
    user_id: UUID
    status: str
    progress: float
    current_step: str | None
    total_steps: int
    parameters: dict
    input_datasets: list[str]
    error_message: str | None
    celery_task_id: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class AnalysisResultCreate(BaseSchema):
    """Analysis result creation schema."""

    result_type: str
    name: str
    description: str | None = None
    data: dict = Field(default_factory=dict)
    summary: dict | None = None
    metrics: dict | None = None
    file_path: str | None = None
    file_type: str | None = None


class AnalysisResultResponse(BaseSchema):
    """Analysis result response schema."""

    id: UUID
    analysis_id: UUID
    result_type: str
    name: str
    description: str | None
    data: dict
    summary: dict | None
    metrics: dict | None
    file_path: str | None
    file_type: str | None
    file_size: int | None
    created_at: datetime


class AnalysisProgress(BaseSchema):
    """Analysis progress update schema."""

    analysis_id: UUID
    status: str
    progress: float
    current_step: str | None
    message: str | None
    timestamp: datetime = None

    def __init__(self, **data):
        if "timestamp" not in data:
            data["timestamp"] = datetime.now(timezone.utc)
        super().__init__(**data)

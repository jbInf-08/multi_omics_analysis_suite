"""Dataset Schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import Field

from backend.app.schemas.common import BaseSchema


class DatasetBase(BaseSchema):
    """Base dataset schema."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    omics_type: str
    data_format: str | None = None


class DatasetCreate(DatasetBase):
    """Dataset creation schema."""

    project_id: UUID
    source: str | None = None
    source_id: str | None = None
    metadata: dict = Field(default_factory=dict)
    clinical_data: dict | None = None
    sample_metadata: dict | None = None


class DatasetUpdate(BaseSchema):
    """Dataset update schema."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    metadata: dict | None = None
    clinical_data: dict | None = None
    sample_metadata: dict | None = None
    status: str | None = None


class DatasetResponse(DatasetBase):
    """Dataset response schema."""

    id: UUID
    project_id: UUID
    status: str
    sample_count: int | None
    feature_count: int | None
    total_size: int | None
    source: str | None
    source_id: str | None
    qc_passed: bool | None
    qc_metrics: dict | None
    preprocessing_applied: list[str]
    normalization_method: str | None
    storage_path: str | None
    storage_type: str
    metadata: dict
    clinical_data: dict | None
    sample_metadata: dict | None
    created_at: datetime
    updated_at: datetime


class DatasetSummary(BaseSchema):
    """Dataset summary for lists."""

    id: UUID
    name: str
    omics_type: str
    status: str
    sample_count: int | None
    feature_count: int | None
    source: str | None
    created_at: datetime


class DatasetUpload(BaseSchema):
    """Dataset upload information."""

    dataset_id: UUID
    upload_url: str
    expires_at: datetime
    max_size: int


class DatasetQC(BaseSchema):
    """Dataset QC results."""

    dataset_id: UUID
    passed: bool
    metrics: dict
    issues: list[dict]
    recommendations: list[str]
    timestamp: datetime

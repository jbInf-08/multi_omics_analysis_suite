"""
Dataset Schemas
"""

from typing import Optional, List
from datetime import datetime
from uuid import UUID

from pydantic import Field

from backend.app.schemas.common import BaseSchema


class DatasetBase(BaseSchema):
    """Base dataset schema."""
    
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    omics_type: str
    data_format: Optional[str] = None


class DatasetCreate(DatasetBase):
    """Dataset creation schema."""
    
    project_id: UUID
    source: Optional[str] = None
    source_id: Optional[str] = None
    metadata: dict = Field(default_factory=dict)
    clinical_data: Optional[dict] = None
    sample_metadata: Optional[dict] = None


class DatasetUpdate(BaseSchema):
    """Dataset update schema."""
    
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    metadata: Optional[dict] = None
    clinical_data: Optional[dict] = None
    sample_metadata: Optional[dict] = None
    status: Optional[str] = None


class DatasetResponse(DatasetBase):
    """Dataset response schema."""
    
    id: UUID
    project_id: UUID
    status: str
    sample_count: Optional[int]
    feature_count: Optional[int]
    total_size: Optional[int]
    source: Optional[str]
    source_id: Optional[str]
    qc_passed: Optional[bool]
    qc_metrics: Optional[dict]
    preprocessing_applied: List[str]
    normalization_method: Optional[str]
    storage_path: Optional[str]
    storage_type: str
    metadata: dict
    clinical_data: Optional[dict]
    sample_metadata: Optional[dict]
    created_at: datetime
    updated_at: datetime


class DatasetSummary(BaseSchema):
    """Dataset summary for lists."""
    
    id: UUID
    name: str
    omics_type: str
    status: str
    sample_count: Optional[int]
    feature_count: Optional[int]
    source: Optional[str]
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
    issues: List[dict]
    recommendations: List[str]
    timestamp: datetime

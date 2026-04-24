"""
Analysis Schemas
"""

from typing import Optional, List, Any
from datetime import datetime, timezone
from uuid import UUID

from pydantic import Field

from backend.app.schemas.common import BaseSchema


class AnalysisBase(BaseSchema):
    """Base analysis schema."""
    
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    analysis_type: str
    omics_types: List[str] = Field(default_factory=list)


class AnalysisCreate(AnalysisBase):
    """Analysis creation schema."""
    
    project_id: UUID
    parameters: dict = Field(default_factory=dict)
    input_datasets: List[UUID] = Field(default_factory=list)


class AnalysisUpdate(BaseSchema):
    """Analysis update schema."""
    
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    parameters: Optional[dict] = None
    status: Optional[str] = None


class AnalysisResponse(AnalysisBase):
    """Analysis response schema."""
    
    id: UUID
    project_id: UUID
    user_id: UUID
    status: str
    progress: float
    current_step: Optional[str]
    total_steps: int
    parameters: dict
    input_datasets: List[str]
    error_message: Optional[str]
    celery_task_id: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]


class AnalysisResultCreate(BaseSchema):
    """Analysis result creation schema."""
    
    result_type: str
    name: str
    description: Optional[str] = None
    data: dict = Field(default_factory=dict)
    summary: Optional[dict] = None
    metrics: Optional[dict] = None
    file_path: Optional[str] = None
    file_type: Optional[str] = None


class AnalysisResultResponse(BaseSchema):
    """Analysis result response schema."""
    
    id: UUID
    analysis_id: UUID
    result_type: str
    name: str
    description: Optional[str]
    data: dict
    summary: Optional[dict]
    metrics: Optional[dict]
    file_path: Optional[str]
    file_type: Optional[str]
    file_size: Optional[int]
    created_at: datetime


class AnalysisProgress(BaseSchema):
    """Analysis progress update schema."""
    
    analysis_id: UUID
    status: str
    progress: float
    current_step: Optional[str]
    message: Optional[str]
    timestamp: datetime = None
    
    def __init__(self, **data):
        if "timestamp" not in data:
            data["timestamp"] = datetime.now(timezone.utc)
        super().__init__(**data)

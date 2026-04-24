"""
Project Schemas
"""

from typing import Optional, List
from datetime import datetime
from uuid import UUID

from pydantic import Field

from backend.app.schemas.common import BaseSchema


class ProjectBase(BaseSchema):
    """Base project schema."""
    
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    project_type: str = "multi_omics"
    omics_types: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    visibility: str = "private"


class ProjectCreate(ProjectBase):
    """Project creation schema."""
    
    config: dict = Field(default_factory=dict)
    metadata: dict = Field(default_factory=dict)


class ProjectUpdate(BaseSchema):
    """Project update schema."""
    
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    omics_types: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    visibility: Optional[str] = None
    config: Optional[dict] = None
    metadata: Optional[dict] = None
    status: Optional[str] = None


class ProjectResponse(ProjectBase):
    """Project response schema."""
    
    id: UUID
    owner_id: UUID
    status: str
    config: dict
    metadata: dict
    collaborators: List[dict]
    created_at: datetime
    updated_at: datetime


class ProjectSummary(BaseSchema):
    """Project summary for lists."""
    
    id: UUID
    name: str
    project_type: str
    omics_types: List[str]
    status: str
    created_at: datetime
    dataset_count: int = 0
    analysis_count: int = 0

"""Project Schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import AliasChoices, Field

from backend.app.schemas.common import BaseSchema


class ProjectBase(BaseSchema):
    """Base project schema."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    project_type: str = "multi_omics"
    omics_types: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    visibility: str = "private"


class ProjectCreate(ProjectBase):
    """Project creation schema."""

    config: dict = Field(default_factory=dict)
    metadata: dict = Field(default_factory=dict)


class ProjectUpdate(BaseSchema):
    """Project update schema."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    omics_types: list[str] | None = None
    tags: list[str] | None = None
    visibility: str | None = None
    config: dict | None = None
    metadata: dict | None = None
    status: str | None = None


class ProjectResponse(ProjectBase):
    """Project response schema."""

    id: UUID
    owner_id: UUID
    status: str
    config: dict
    # The ORM attribute is ``project_metadata`` (``metadata`` is reserved by the
    # SQLAlchemy Declarative base); serialize it under the public name ``metadata``.
    metadata: dict = Field(
        default_factory=dict, validation_alias=AliasChoices("project_metadata", "metadata")
    )
    collaborators: list[dict]
    created_at: datetime
    updated_at: datetime


class ProjectSummary(BaseSchema):
    """Project summary for lists."""

    id: UUID
    name: str
    project_type: str
    omics_types: list[str]
    status: str
    created_at: datetime
    dataset_count: int = 0
    analysis_count: int = 0

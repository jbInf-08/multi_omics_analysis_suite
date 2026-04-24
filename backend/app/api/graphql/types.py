"""
GraphQL Types
"""

from typing import List, Optional
from datetime import datetime
import strawberry


@strawberry.type
class UserType:
    """User GraphQL type."""
    id: strawberry.ID
    email: str
    username: str
    full_name: Optional[str]
    organization: Optional[str]
    is_active: bool
    is_verified: bool
    roles: List[str]
    created_at: datetime
    updated_at: datetime


@strawberry.type
class ProjectType:
    """Project GraphQL type."""
    id: strawberry.ID
    name: str
    description: Optional[str]
    project_type: str
    omics_types: List[str]
    status: str
    visibility: str
    tags: List[str]
    owner_id: strawberry.ID
    created_at: datetime
    updated_at: datetime


@strawberry.type
class DatasetType:
    """Dataset GraphQL type."""
    id: strawberry.ID
    name: str
    description: Optional[str]
    omics_type: str
    data_format: Optional[str]
    sample_count: Optional[int]
    feature_count: Optional[int]
    status: str
    source: Optional[str]
    qc_passed: Optional[bool]
    project_id: strawberry.ID
    created_at: datetime
    updated_at: datetime


@strawberry.type
class AnalysisType:
    """Analysis GraphQL type."""
    id: strawberry.ID
    name: str
    description: Optional[str]
    analysis_type: str
    omics_types: List[str]
    status: str
    progress: float
    current_step: Optional[str]
    total_steps: int
    project_id: strawberry.ID
    user_id: strawberry.ID
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]


@strawberry.type
class AnalysisResultType:
    """Analysis result GraphQL type."""
    id: strawberry.ID
    result_type: str
    name: str
    description: Optional[str]
    data: strawberry.scalars.JSON
    summary: Optional[strawberry.scalars.JSON]
    metrics: Optional[strawberry.scalars.JSON]
    file_path: Optional[str]
    analysis_id: strawberry.ID
    created_at: datetime


@strawberry.type
class OmicsModuleType:
    """Omics module GraphQL type."""
    name: str
    category: str
    description: str
    version: str
    is_active: bool
    supported_formats: List[str]
    available_pipelines: List[str]
    available_analyses: List[str]


@strawberry.type
class PipelineType:
    """Pipeline GraphQL type."""
    id: strawberry.ID
    name: str
    description: Optional[str]
    version: str
    omics_types: List[str]
    steps: List[strawberry.scalars.JSON]
    is_active: bool
    is_public: bool
    created_at: datetime


@strawberry.type
class PipelineRunType:
    """Pipeline run GraphQL type."""
    id: strawberry.ID
    pipeline_id: strawberry.ID
    status: str
    progress: float
    current_step: int
    current_step_name: Optional[str]
    error_message: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]


@strawberry.type
class MLModelType:
    """ML Model GraphQL type."""
    name: str
    model_type: str
    description: str
    supported_omics: List[str]
    parameters: strawberry.scalars.JSON


@strawberry.input
class ProjectInput:
    """Project creation input."""
    name: str
    description: Optional[str] = None
    project_type: str = "multi_omics"
    omics_types: List[str] = strawberry.field(default_factory=list)
    tags: List[str] = strawberry.field(default_factory=list)
    visibility: str = "private"


@strawberry.input
class DatasetInput:
    """Dataset creation input."""
    name: str
    description: Optional[str] = None
    omics_type: str
    data_format: Optional[str] = None
    project_id: strawberry.ID
    source: Optional[str] = None


@strawberry.input
class AnalysisInput:
    """Analysis creation input."""
    name: str
    description: Optional[str] = None
    analysis_type: str
    omics_types: List[str]
    project_id: strawberry.ID
    parameters: Optional[strawberry.scalars.JSON] = None
    input_datasets: List[strawberry.ID] = strawberry.field(default_factory=list)

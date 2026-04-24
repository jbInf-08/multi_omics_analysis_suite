"""GraphQL Types."""

from datetime import datetime

import strawberry


@strawberry.type
class UserType:
    """User GraphQL type."""

    id: strawberry.ID
    email: str
    username: str
    full_name: str | None
    organization: str | None
    is_active: bool
    is_verified: bool
    roles: list[str]
    created_at: datetime
    updated_at: datetime


@strawberry.type
class ProjectType:
    """Project GraphQL type."""

    id: strawberry.ID
    name: str
    description: str | None
    project_type: str
    omics_types: list[str]
    status: str
    visibility: str
    tags: list[str]
    owner_id: strawberry.ID
    created_at: datetime
    updated_at: datetime


@strawberry.type
class DatasetType:
    """Dataset GraphQL type."""

    id: strawberry.ID
    name: str
    description: str | None
    omics_type: str
    data_format: str | None
    sample_count: int | None
    feature_count: int | None
    status: str
    source: str | None
    qc_passed: bool | None
    project_id: strawberry.ID
    created_at: datetime
    updated_at: datetime


@strawberry.type
class AnalysisType:
    """Analysis GraphQL type."""

    id: strawberry.ID
    name: str
    description: str | None
    analysis_type: str
    omics_types: list[str]
    status: str
    progress: float
    current_step: str | None
    total_steps: int
    project_id: strawberry.ID
    user_id: strawberry.ID
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


@strawberry.type
class AnalysisResultType:
    """Analysis result GraphQL type."""

    id: strawberry.ID
    result_type: str
    name: str
    description: str | None
    data: strawberry.scalars.JSON
    summary: strawberry.scalars.JSON | None
    metrics: strawberry.scalars.JSON | None
    file_path: str | None
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
    supported_formats: list[str]
    available_pipelines: list[str]
    available_analyses: list[str]


@strawberry.type
class PipelineType:
    """Pipeline GraphQL type."""

    id: strawberry.ID
    name: str
    description: str | None
    version: str
    omics_types: list[str]
    steps: list[strawberry.scalars.JSON]
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
    current_step_name: str | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


@strawberry.type
class MLModelType:
    """ML Model GraphQL type."""

    name: str
    model_type: str
    description: str
    supported_omics: list[str]
    parameters: strawberry.scalars.JSON


@strawberry.input
class ProjectInput:
    """Project creation input."""

    name: str
    description: str | None = None
    project_type: str = "multi_omics"
    omics_types: list[str] = strawberry.field(default_factory=list)
    tags: list[str] = strawberry.field(default_factory=list)
    visibility: str = "private"


@strawberry.input
class DatasetInput:
    """Dataset creation input."""

    name: str
    description: str | None = None
    omics_type: str
    data_format: str | None = None
    project_id: strawberry.ID
    source: str | None = None


@strawberry.input
class AnalysisInput:
    """Analysis creation input."""

    name: str
    description: str | None = None
    analysis_type: str
    omics_types: list[str]
    project_id: strawberry.ID
    parameters: strawberry.scalars.JSON | None = None
    input_datasets: list[strawberry.ID] = strawberry.field(default_factory=list)

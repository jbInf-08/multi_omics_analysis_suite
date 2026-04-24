"""Pipeline Routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.core.security import TokenPayload, get_current_user
from backend.app.models.pipeline import Pipeline, PipelineRun, PipelineStatus
from backend.app.schemas.common import PaginatedResponse

router = APIRouter()


class PipelineCreate(BaseModel):
    """Pipeline creation schema."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    omics_types: list[str] = Field(default_factory=list)
    steps: list[dict] = Field(default_factory=list)
    default_parameters: dict = Field(default_factory=dict)
    timeout_seconds: int = 3600
    max_retries: int = 3
    tags: list[str] = Field(default_factory=list)


class PipelineResponse(BaseModel):
    """Pipeline response schema."""

    id: UUID
    name: str
    description: str | None
    version: str
    omics_types: list[str]
    steps: list[dict]
    default_parameters: dict
    timeout_seconds: int
    max_retries: int
    author: str | None
    tags: list[str]
    is_active: bool
    is_public: bool

    class Config:
        from_attributes = True


class PipelineRunCreate(BaseModel):
    """Pipeline run creation schema."""

    pipeline_id: UUID
    parameters: dict = Field(default_factory=dict)
    analysis_id: UUID | None = None


class PipelineRunResponse(BaseModel):
    """Pipeline run response schema."""

    id: UUID
    pipeline_id: UUID
    status: str
    progress: float
    current_step: int
    current_step_name: str | None
    parameters: dict
    step_results: list[dict]
    error_message: str | None
    error_step: int | None
    retry_count: int
    celery_task_id: str | None

    class Config:
        from_attributes = True


@router.post("/", response_model=PipelineResponse, status_code=status.HTTP_201_CREATED)
async def create_pipeline(
    pipeline_data: PipelineCreate,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new pipeline."""
    # Check if name exists
    result = await db.execute(select(Pipeline).where(Pipeline.name == pipeline_data.name))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Pipeline with this name already exists",
        )

    pipeline = Pipeline(
        name=pipeline_data.name,
        description=pipeline_data.description,
        omics_types=pipeline_data.omics_types,
        steps=pipeline_data.steps,
        default_parameters=pipeline_data.default_parameters,
        timeout_seconds=pipeline_data.timeout_seconds,
        max_retries=pipeline_data.max_retries,
        tags=pipeline_data.tags,
        author=current_user.sub,
    )

    db.add(pipeline)
    await db.commit()
    await db.refresh(pipeline)

    return pipeline


@router.get("/", response_model=PaginatedResponse[PipelineResponse])
async def list_pipelines(
    omics_type: str | None = None,
    tag: str | None = None,
    public_only: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List available pipelines."""
    query = select(Pipeline).where(Pipeline.is_active)
    count_query = select(func.count(Pipeline.id)).where(Pipeline.is_active)

    if public_only:
        query = query.where(Pipeline.is_public)
        count_query = count_query.where(Pipeline.is_public)

    if omics_type:
        query = query.where(Pipeline.omics_types.contains([omics_type]))
        count_query = count_query.where(Pipeline.omics_types.contains([omics_type]))

    if tag:
        query = query.where(Pipeline.tags.contains([tag]))
        count_query = count_query.where(Pipeline.tags.contains([tag]))

    # Count total
    count_result = await db.execute(count_query)
    total = count_result.scalar()

    # Get paginated results
    offset = (page - 1) * page_size
    result = await db.execute(query.order_by(Pipeline.name).offset(offset).limit(page_size))
    pipelines = result.scalars().all()

    pages = (total + page_size - 1) // page_size if total > 0 else 1

    return PaginatedResponse(
        items=pipelines,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
        has_next=page < pages,
        has_prev=page > 1,
    )


@router.get("/{pipeline_id}", response_model=PipelineResponse)
async def get_pipeline(
    pipeline_id: UUID,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get pipeline by ID."""
    result = await db.execute(select(Pipeline).where(Pipeline.id == pipeline_id))
    pipeline = result.scalar_one_or_none()

    if not pipeline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pipeline not found",
        )

    return pipeline


@router.post("/run", response_model=PipelineRunResponse, status_code=status.HTTP_201_CREATED)
async def run_pipeline(
    run_data: PipelineRunCreate,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Start a pipeline run."""
    # Verify pipeline exists
    result = await db.execute(select(Pipeline).where(Pipeline.id == run_data.pipeline_id))
    pipeline = result.scalar_one_or_none()

    if not pipeline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pipeline not found",
        )

    if not pipeline.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Pipeline is not active",
        )

    # Merge default parameters with provided parameters
    parameters = {**pipeline.default_parameters, **run_data.parameters}

    # Create pipeline run
    run = PipelineRun(
        pipeline_id=run_data.pipeline_id,
        analysis_id=run_data.analysis_id,
        parameters=parameters,
        status=PipelineStatus.PENDING,
    )

    db.add(run)
    await db.commit()
    await db.refresh(run)

    # Start Celery task
    from backend.app.tasks.analysis_tasks import run_pipeline

    task = run_pipeline.delay(
        pipeline_id=str(run_data.pipeline_id),
        run_id=str(run.id),
        parameters=parameters,
    )

    # Update with task ID
    run.celery_task_id = task.id
    run.status = PipelineStatus.RUNNING
    await db.commit()
    await db.refresh(run)

    return run


@router.get("/runs/{run_id}", response_model=PipelineRunResponse)
async def get_pipeline_run(
    run_id: UUID,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get pipeline run status."""
    result = await db.execute(select(PipelineRun).where(PipelineRun.id == run_id))
    run = result.scalar_one_or_none()

    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pipeline run not found",
        )

    return run


@router.post("/runs/{run_id}/cancel", response_model=PipelineRunResponse)
async def cancel_pipeline_run(
    run_id: UUID,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancel a pipeline run."""
    result = await db.execute(select(PipelineRun).where(PipelineRun.id == run_id))
    run = result.scalar_one_or_none()

    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pipeline run not found",
        )

    if run.status not in [PipelineStatus.PENDING, PipelineStatus.QUEUED, PipelineStatus.RUNNING]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Pipeline run cannot be cancelled",
        )

    # Cancel Celery task if running
    if hasattr(run, "celery_task_id") and run.celery_task_id:
        try:
            from backend.app.core.celery_app import celery_app

            celery_app.control.revoke(run.celery_task_id, terminate=True)
        except Exception as e:
            # Log but don't fail
            import logging

            logging.warning(f"Failed to revoke Celery task: {e}")

    run.status = PipelineStatus.CANCELLED
    from datetime import datetime, timezone

    run.completed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(run)

    return run

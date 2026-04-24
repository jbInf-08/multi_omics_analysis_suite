"""Omics Module Routes."""

import logging
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.core.security import TokenPayload, get_current_user
from backend.app.models.analysis import Analysis, AnalysisStatus, AnalysisType, utc_now
from backend.app.models.project import Project
from backend.app.schemas.analysis import AnalysisResponse

logger = logging.getLogger(__name__)

router = APIRouter()


class OmicsModuleInfo(BaseModel):
    """Omics module information."""

    name: str
    category: str
    description: str
    version: str
    is_active: bool
    supported_formats: list[str]
    available_pipelines: list[str]
    available_analyses: list[str]


class OmicsCategoryInfo(BaseModel):
    """Omics category information."""

    name: str
    description: str
    modules: list[str]
    module_count: int


class OmicsModuleAnalyzeRequest(BaseModel):
    """Body for starting a module-scoped analysis (creates an Analysis row and queues Celery)."""

    project_id: UUID
    analysis_type: str = Field(
        ..., min_length=1, description="Registered analysis name for this module"
    )
    parameters: dict = Field(default_factory=dict)
    dataset_ids: list[UUID] = Field(default_factory=list)


@router.get("/modules", response_model=list[OmicsModuleInfo])
async def list_omics_modules(
    request: Request,
    category: str | None = None,
    active_only: bool = True,
    current_user: TokenPayload = Depends(get_current_user),
) -> list[OmicsModuleInfo]:
    """List all available omics modules."""
    registry = request.app.state.omics_registry
    modules = registry.list_modules(category=category, active_only=active_only)

    return [
        OmicsModuleInfo(
            name=m.name,
            category=m.category.value,
            description=m.description,
            version=m.version,
            is_active=m.is_active,
            supported_formats=m.supported_formats,
            available_pipelines=[p.name for p in m.get_available_pipelines()],
            available_analyses=[a.name for a in m.get_available_analyses()],
        )
        for m in modules
    ]


@router.get("/categories", response_model=list[OmicsCategoryInfo])
async def list_omics_categories(
    request: Request,
    current_user: TokenPayload = Depends(get_current_user),
) -> list[OmicsCategoryInfo]:
    """List all omics categories."""
    registry = request.app.state.omics_registry
    categories = registry.list_categories()

    return [
        OmicsCategoryInfo(
            name=cat.value,
            description=cat.description,
            modules=registry.get_modules_by_category(cat),
            module_count=len(registry.get_modules_by_category(cat)),
        )
        for cat in categories
    ]


@router.get("/modules/{module_name}", response_model=OmicsModuleInfo)
async def get_omics_module(
    module_name: str,
    request: Request,
    current_user: TokenPayload = Depends(get_current_user),
) -> OmicsModuleInfo:
    """Get specific omics module information."""
    registry = request.app.state.omics_registry
    module = registry.get_module(module_name)

    if not module:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Omics module '{module_name}' not found",
        )

    return OmicsModuleInfo(
        name=module.name,
        category=module.category.value,
        description=module.description,
        version=module.version,
        is_active=module.is_active,
        supported_formats=module.supported_formats,
        available_pipelines=[p.name for p in module.get_available_pipelines()],
        available_analyses=[a.name for a in module.get_available_analyses()],
    )


@router.get("/modules/{module_name}/pipelines")
async def get_module_pipelines(
    module_name: str,
    request: Request,
    current_user: TokenPayload = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """Get available pipelines for an omics module."""
    registry = request.app.state.omics_registry
    module = registry.get_module(module_name)

    if not module:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Omics module '{module_name}' not found",
        )

    pipelines = module.get_available_pipelines()
    return [
        {
            "name": p.name,
            "description": p.description,
            "steps": p.steps,
            "default_parameters": p.default_parameters,
        }
        for p in pipelines
    ]


@router.get("/modules/{module_name}/analyses")
async def get_module_analyses(
    module_name: str,
    request: Request,
    current_user: TokenPayload = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """Get available analyses for an omics module."""
    registry = request.app.state.omics_registry
    module = registry.get_module(module_name)

    if not module:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Omics module '{module_name}' not found",
        )

    analyses = module.get_available_analyses()
    return [
        {
            "name": a.name,
            "description": a.description,
            "parameters": a.parameters,
            "output_types": a.output_types,
        }
        for a in analyses
    ]


@router.post(
    "/modules/{module_name}/analyze",
    response_model=AnalysisResponse,
    status_code=status.HTTP_201_CREATED,
)
async def run_module_analysis(
    module_name: str,
    body: OmicsModuleAnalyzeRequest,
    request: Request,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Analysis:
    """Run an analysis for a registered omics module (same Celery pipeline as POST /analyses/)."""
    registry = request.app.state.omics_registry
    module = registry.get_module(module_name)

    if not module:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Omics module '{module_name}' not found",
        )

    allowed = {a.name for a in module.get_available_analyses()}
    if body.analysis_type not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Analysis '{body.analysis_type}' is not available for module '{module.name}'. "
            f"Choose one of: {sorted(allowed)}",
        )

    result = await db.execute(select(Project).where(Project.id == body.project_id))
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    if str(project.owner_id) != current_user.sub:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to create analyses in this project",
        )

    merged_params = {
        **body.parameters,
        "omics_execute_analysis_type": body.analysis_type,
        "omics_module": module.name,
    }

    analysis = Analysis(
        id=uuid4(),
        name=f"{module.name}: {body.analysis_type}",
        description=f"Module analysis {body.analysis_type} on {module.name}",
        analysis_type=AnalysisType.SINGLE_OMICS,
        omics_types=[module.name],
        parameters=merged_params,
        input_datasets=[str(d) for d in body.dataset_ids],
        project_id=body.project_id,
        user_id=UUID(current_user.sub),
        status=AnalysisStatus.PENDING,
        progress=0.0,
        total_steps=0,
        created_at=utc_now(),
    )

    db.add(analysis)
    await db.commit()
    await db.refresh(analysis)

    try:
        from backend.app.tasks.analysis_tasks import run_analysis

        task = run_analysis.apply_async(
            args=[str(analysis.id)],
            kwargs={"parameters": {}},
            queue="analysis",
        )

        analysis.celery_task_id = task.id
        analysis.status = AnalysisStatus.QUEUED
        await db.commit()
        await db.refresh(analysis)

        logger.info(
            "Analysis %s queued from omics module %s (task %s)", analysis.id, module.name, task.id
        )

    except Exception as exc:
        logger.error("Failed to queue analysis %s: %s", analysis.id, exc)
        analysis.status = AnalysisStatus.FAILED
        analysis.error_message = f"Failed to queue task: {exc!s}"
        await db.commit()
        await db.refresh(analysis)

    return analysis

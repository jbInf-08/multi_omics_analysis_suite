"""Omics Module Routes."""

import logging
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.core.security import TokenPayload, get_current_user
from backend.app.models.analysis import Analysis, AnalysisStatus, AnalysisType, utc_now
from backend.app.models.dataset import Dataset
from backend.app.models.project import Project
from backend.app.schemas.analysis import AnalysisResponse

if TYPE_CHECKING:  # imports used for annotations only
    import numpy as np
    import pandas as pd

    from backend.omics.integration.data_fusion import DataFusion

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


# ---------------------------------------------------------------------------
# Multi-omics integration
# ---------------------------------------------------------------------------


class OmicsIntegrationRequest(BaseModel):
    """Body for running a multi-omics integration over stored datasets."""

    project_id: UUID
    dataset_ids: list[UUID] = Field(..., min_length=2, description="At least two datasets")
    method: str = Field("intermediate_fusion", description="Fusion method identifier")
    n_components: int = Field(10, ge=2, le=100)


class OmicsContribution(BaseModel):
    """One omics block's share of the integrated signal."""

    dataset_id: UUID
    dataset_name: str
    omics_type: str
    contribution: float = Field(..., description="Share of the integrated signal, 0-1")


class IntegrationSamplePoint(BaseModel):
    """A sample positioned in the first two dimensions of the fused space."""

    sample: str
    x: float
    y: float
    cluster: int


class OmicsIntegrationResponse(BaseModel):
    """Computed result of a multi-omics integration."""

    method: str
    n_samples: int
    n_features: int
    n_omics: int
    variance_explained: float | None = Field(
        None, description="Share of variance retained by the fused representation, 0-1"
    )
    contribution_basis: str = Field(
        ...,
        description=(
            "How contributions were derived. 'pca_loadings' attributes retained "
            "variance via component loadings; 'scaled_variance_share' is only a "
            "feature-count proxy and is not a signal measure."
        ),
    )
    contributions: list[OmicsContribution]
    n_clusters: int
    embedding: list[IntegrationSamplePoint]


#: Method identifiers the UI offers, mapped to the fusion implementations that
#: are wired up. Anything else is rejected rather than silently falling back to
#: a different method than the caller asked for.
_SUPPORTED_FUSION_METHODS = {"early_fusion", "intermediate_fusion"}


def _load_dataset_frame(storage_path: str) -> "pd.DataFrame":
    """Read a dataset's persisted matrix. Blocking; call via a worker thread."""
    import pandas as pd

    return pd.read_parquet(storage_path)


def _cluster_fused(fused: "np.ndarray", max_k: int = 8) -> tuple[int, list[int]]:
    """Pick k by silhouette score and return (k, labels).

    Reports a single cluster when there are too few samples to score one, rather
    than inventing a partition.
    """
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score

    n_samples = int(fused.shape[0])
    if n_samples < 4:
        return 1, [0] * n_samples

    best_k, best_score, best_labels = 1, -1.0, [0] * n_samples
    for k in range(2, min(max_k, n_samples - 1) + 1):
        labels = KMeans(n_clusters=k, n_init=10, random_state=42).fit_predict(fused)
        if len(set(labels)) < 2:
            continue
        score = float(silhouette_score(fused, labels))
        if score > best_score:
            best_k, best_score, best_labels = k, score, [int(x) for x in labels]

    return best_k, best_labels


@router.post("/integrate", response_model=OmicsIntegrationResponse)
async def integrate_omics(
    body: OmicsIntegrationRequest,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OmicsIntegrationResponse:
    """Run a multi-omics integration and return the computed result.

    Synchronous on purpose: the fusion is an in-memory scikit-learn
    decomposition over already-materialised matrices, and the caller renders the
    result directly. Long-running module analyses still go through Celery via
    POST /modules/{module_name}/analyze.
    """
    if body.method not in _SUPPORTED_FUSION_METHODS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Integration method '{body.method}' is not implemented. "
                f"Choose one of: {sorted(_SUPPORTED_FUSION_METHODS)}"
            ),
        )

    result = await db.execute(select(Project).where(Project.id == body.project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    if str(project.owner_id) != current_user.sub:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to read datasets in this project",
        )

    result = await db.execute(
        select(Dataset).where(
            Dataset.id.in_(body.dataset_ids), Dataset.project_id == body.project_id
        )
    )
    datasets = list(result.scalars().all())

    found = {d.id for d in datasets}
    missing = [str(d) for d in body.dataset_ids if d not in found]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Datasets not found in this project: {missing}",
        )

    unreadable = [d.name for d in datasets if not d.storage_path]
    if unreadable:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Datasets have no stored data yet: {unreadable}",
        )

    from starlette.concurrency import run_in_threadpool

    from backend.omics.base.omics_base import OmicsData
    from backend.omics.integration.data_fusion import EarlyFusion, IntermediateFusion

    # Keyed by dataset id so two datasets of the same omics type stay distinct.
    omics_inputs: dict[str, OmicsData] = {}
    by_key: dict[str, Dataset] = {}
    total_features = 0

    for dataset in datasets:
        try:
            frame = await run_in_threadpool(_load_dataset_frame, dataset.storage_path)
        except Exception as exc:
            logger.error(
                "Failed to read dataset %s at %s: %s", dataset.id, dataset.storage_path, exc
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Could not read stored data for dataset '{dataset.name}'",
            ) from exc

        frame = frame.select_dtypes(include="number")
        if frame.empty:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Dataset '{dataset.name}' has no numeric features to integrate",
            )

        key = str(dataset.id)
        by_key[key] = dataset
        total_features += int(frame.shape[1])
        omics_inputs[key] = OmicsData(
            data=frame,
            feature_names=[str(c) for c in frame.columns],
            sample_names=[str(i) for i in frame.index],
            data_type=getattr(dataset.omics_type, "value", str(dataset.omics_type)),
        )

    model: DataFusion
    if body.method == "early_fusion":
        model = EarlyFusion(reduce_dim=body.n_components)
    else:
        model = IntermediateFusion(n_components=body.n_components)

    try:
        fusion = await run_in_threadpool(model.fit_transform, omics_inputs)
    except ValueError as exc:
        # _align_samples raises when the datasets share no sample identifiers.
        logger.info("Integration rejected for project %s: %s", body.project_id, exc)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Datasets could not be aligned. They must share sample identifiers "
                f"in their row index. ({exc})"
            ),
        ) from exc

    if fusion.fused_data.shape[0] == 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The selected datasets share no common samples, so they cannot be integrated.",
        )

    n_clusters, labels = await run_in_threadpool(_cluster_fused, fusion.fused_data)

    variance_explained = fusion.metadata.get("total_variance_explained")
    if variance_explained is None:
        variance_explained = fusion.metadata.get("variance_explained")
    if isinstance(variance_explained, list):
        variance_explained = float(sum(variance_explained))

    contributions = [
        OmicsContribution(
            dataset_id=by_key[key].id,
            dataset_name=by_key[key].name,
            omics_type=getattr(by_key[key].omics_type, "value", str(by_key[key].omics_type)),
            contribution=float(share),
        )
        for key, share in (fusion.omics_contributions or {}).items()
    ]

    embedding = [
        IntegrationSamplePoint(
            sample=sample,
            x=float(fusion.fused_data[i, 0]),
            y=float(fusion.fused_data[i, 1]) if fusion.fused_data.shape[1] > 1 else 0.0,
            cluster=labels[i],
        )
        for i, sample in enumerate(fusion.sample_names)
    ]

    return OmicsIntegrationResponse(
        method=fusion.method,
        n_samples=int(fusion.fused_data.shape[0]),
        n_features=total_features,
        n_omics=len(omics_inputs),
        variance_explained=variance_explained,
        contribution_basis=str(fusion.metadata.get("contribution_basis", "unknown")),
        contributions=contributions,
        n_clusters=n_clusters,
        embedding=embedding,
    )

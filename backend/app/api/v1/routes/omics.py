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
    n_components: int = Field(
        10,
        ge=2,
        le=100,
        description=(
            "Components retained by the decomposition methods. Contributions are "
            "shares of the variance these components retain, so this changes what "
            "they mean; ignored by the network methods."
        ),
    )
    pathway_file: str | None = Field(
        None,
        description=(
            "Path to a GMT file of pathway definitions. Required by "
            "pathway_integration -- the built-in sets are illustrative examples "
            "and are not a basis for interpreting real data."
        ),
    )


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


#: Methods backed by a joint decomposition. These produce a sample x component
#: matrix, so variance explained is meaningful and contributions come from the
#: component loadings.
_DECOMPOSITION_METHODS = {"early_fusion", "intermediate_fusion"}

#: Methods backed by a sample-similarity network. These produce a samples x
#: samples matrix instead, so there is no variance to explain; samples are
#: positioned by spectral embedding and contributions measure how far each
#: omics' own similarity structure agrees with the consensus.
_NETWORK_METHODS = {"snf", "network_integration"}

#: Pathway-level integration. Kept separate because it needs pathway
#: definitions supplied by the caller.
_PATHWAY_METHODS = {"pathway_integration"}

#: Anything else is rejected rather than silently falling back to a different
#: method than the caller asked for.
_SUPPORTED_FUSION_METHODS = _DECOMPOSITION_METHODS | _NETWORK_METHODS | _PATHWAY_METHODS


def _for_log(value: object, limit: int = 200) -> str:
    """Flatten a value to a single safe line for logging.

    Messages here can carry data read from user-uploaded files -- sample
    identifiers taken from a parquet row index, pandas' own error text -- so
    newlines and control characters are stripped before logging. Without that,
    a crafted identifier could inject additional log lines.
    """
    # The explicit newline replacement is deliberate and comes first: it is the
    # form CodeQL's py/log-injection query recognises as a sanitiser, and it is
    # what actually prevents a forged log line. The isprintable pass then takes
    # care of the remaining control characters.
    text = str(value).replace("\r", " ").replace("\n", " ")
    cleaned = "".join(ch if ch.isprintable() else " " for ch in text)
    if len(cleaned) > limit:
        cleaned = cleaned[: limit - 1] + "…"
    return cleaned


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


def _spectral_coordinates(fused: "np.ndarray") -> "np.ndarray":
    """Place samples in 2D from a similarity matrix.

    Uses the leading eigenvectors of the normalised affinity, which is the
    standard spectral embedding. Falls back to zeros when the matrix is too
    small or degenerate to decompose, so the caller still gets one point per
    sample rather than an error.
    """
    import numpy as np

    n = fused.shape[0]
    if n < 3:
        return np.zeros((n, 2))

    affinity = np.asarray(fused, dtype=float)
    affinity = (affinity + affinity.T) / 2.0  # enforce symmetry
    degree = affinity.sum(axis=1)
    degree[degree == 0] = 1.0
    normalised = affinity / np.sqrt(np.outer(degree, degree))

    try:
        eigenvalues, eigenvectors = np.linalg.eigh(normalised)
    except np.linalg.LinAlgError:
        return np.zeros((n, 2))

    # Largest eigenvalues last from eigh; skip the trivial leading component.
    order = np.argsort(eigenvalues)[::-1]
    picked = order[1:3] if len(order) >= 3 else order[:2]
    coords = eigenvectors[:, picked]
    if coords.shape[1] < 2:
        coords = np.hstack([coords, np.zeros((n, 2 - coords.shape[1]))])
    return coords


def _cluster_network(fused: "np.ndarray", max_k: int = 8) -> tuple[int, list[int]]:
    """Spectral clustering on a similarity matrix, k chosen by silhouette.

    Mirrors _cluster_fused but scores on the precomputed affinity rather than a
    coordinate matrix. Reports a single cluster when there are too few samples
    to score one.
    """
    import numpy as np
    from sklearn.cluster import SpectralClustering
    from sklearn.metrics import silhouette_score

    n = int(fused.shape[0])
    if n < 4:
        return 1, [0] * n

    affinity = np.asarray(fused, dtype=float)
    affinity = (affinity + affinity.T) / 2.0
    # silhouette_score needs a distance; affinity is a similarity.
    spread = affinity.max() or 1.0
    distance = spread - affinity
    np.fill_diagonal(distance, 0.0)

    best_k, best_score, best_labels = 1, -1.0, [0] * n
    for k in range(2, min(max_k, n - 1) + 1):
        try:
            labels = SpectralClustering(
                n_clusters=k, affinity="precomputed", random_state=42
            ).fit_predict(affinity)
        except Exception:
            continue
        if len(set(labels)) < 2:
            continue
        score = float(silhouette_score(distance, labels, metric="precomputed"))
        if score > best_score:
            best_k, best_score, best_labels = k, score, [int(x) for x in labels]

    return best_k, best_labels


async def _integrate_by_network(
    body: OmicsIntegrationRequest,
    omics_inputs: dict,
    by_key: dict,
    total_features: int,
) -> OmicsIntegrationResponse:
    """Integrate through a fused sample-similarity network.

    Covers snf (Wang et al., Nature Methods 2014) and the co-expression style
    sample network. Both yield a samples x samples matrix rather than a
    sample x component one, so there is no variance to report: samples are
    positioned by spectral embedding and clustered spectrally, and
    contributions measure agreement with the consensus network instead of
    retained variance. The response records that difference in
    contribution_basis so the two are not read as the same quantity.
    """
    from starlette.concurrency import run_in_threadpool

    from backend.omics.integration.network_integration import (
        NetworkIntegrator,
        NetworkResult,
        SimilarityNetworkFusion,
    )

    def _run() -> "NetworkResult":
        if body.method == "snf":
            return SimilarityNetworkFusion().fuse(omics_inputs)

        # network_integration: build one sample network per omics, then take
        # their mean as the consensus. NetworkIntegrator.build_sample_network is
        # the repo's own construction, so this stays consistent with it.
        import numpy as np

        from backend.omics.base.omics_base import OmicsData
        from backend.omics.integration.data_fusion import EarlyFusion

        # build_sample_network reads data.data.values directly, so the blocks
        # must be restricted to shared samples first or the per-omics matrices
        # come out different sizes and cannot be averaged.
        aligned = EarlyFusion()._align_samples(omics_inputs)
        shared = list(next(iter(aligned.values())).index)

        integrator = NetworkIntegrator()
        individual = {
            name: np.asarray(
                integrator.build_sample_network(
                    OmicsData(
                        data=frame,
                        feature_names=[str(c) for c in frame.columns],
                        sample_names=[str(i) for i in frame.index],
                        data_type=name,
                    )
                )
            )
            for name, frame in aligned.items()
        }
        stacked = np.stack(list(individual.values()))
        fused = stacked.mean(axis=0)

        return NetworkResult(
            fused_network=fused,
            sample_names=[str(x) for x in shared],
            individual_networks=individual,
            metadata={"method": "network_integration"},
        )

    try:
        result = await run_in_threadpool(_run)
    except ValueError as exc:
        logger.info(
            "Network integration rejected for project %s: %s",
            _for_log(body.project_id),
            _for_log(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Datasets could not be aligned. They must share sample identifiers "
                "in their row index."
            ),
        ) from exc

    fused = result.fused_network
    if fused.shape[0] == 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The selected datasets share no common samples, so they cannot be integrated.",
        )

    coords = await run_in_threadpool(_spectral_coordinates, fused)
    n_clusters, labels = await run_in_threadpool(_cluster_network, fused)

    return OmicsIntegrationResponse(
        method=body.method,
        n_samples=int(fused.shape[0]),
        n_features=total_features,
        n_omics=len(omics_inputs),
        # A similarity network has no decomposition, so nothing to report here
        # rather than a number that would not mean what the label says.
        variance_explained=None,
        contribution_basis="not_applicable",
        # No per-omics attribution is reported for the network methods. The
        # obvious candidate -- correlating each input network against the fused
        # one -- is not trustworthy: SNF iterates the inputs toward each other,
        # and the resulting share moved from 0.00 to 0.44 for the same noise
        # block simply by changing its feature count. Leave-one-out influence
        # would be sounder but needs a fusion per omics. Rather than draw a bar
        # chart from a number that does not hold up, this stays empty and the UI
        # says so.
        contributions=[],
        n_clusters=n_clusters,
        embedding=[
            IntegrationSamplePoint(
                sample=sample,
                x=float(coords[i, 0]),
                y=float(coords[i, 1]),
                cluster=labels[i],
            )
            for i, sample in enumerate(result.sample_names)
        ],
    )


async def _integrate_by_pathway(
    body: OmicsIntegrationRequest,
    omics_inputs: dict,
    by_key: dict,
    total_features: int,
) -> OmicsIntegrationResponse:
    """Integrate at the pathway level.

    Requires pathway definitions from the caller. PathwayIntegrator will happily
    fall back to eight hardcoded example gene sets of a few genes each, which
    its own source calls "Simplified example pathways" -- scoring real data
    against those would produce numbers that look like results and are not, so
    the request is refused instead.
    """
    import numpy as np
    from starlette.concurrency import run_in_threadpool

    from backend.omics.integration.data_fusion import DataFusion
    from backend.omics.integration.pathway_integration import PathwayIntegrator

    if not body.pathway_file:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "pathway_integration needs pathway definitions: supply pathway_file "
                "with a GMT file. The built-in sets are illustrative examples, not a "
                "basis for interpreting real data."
            ),
        )

    def _run() -> tuple[dict, "np.ndarray"]:
        import numpy as np

        integrator = PathwayIntegrator().load_pathways(body.pathway_file)
        scores = {
            name: integrator.compute_pathway_scores(data) for name, data in omics_inputs.items()
        }
        # Pathway scores are samples x pathways per omics; concatenating gives a
        # joint pathway-space representation the same shape as a fused matrix.
        frames = [np.asarray(getattr(s, "scores", s)) for s in scores.values()]
        return scores, np.hstack(frames)

    try:
        per_omics, joint = await run_in_threadpool(_run)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Pathway file not found: {_for_log(body.pathway_file)}",
        ) from exc
    except ValueError as exc:
        logger.info(
            "Pathway integration rejected for project %s: %s",
            _for_log(body.project_id),
            _for_log(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Datasets could not be integrated at pathway level. They must share "
                "sample identifiers and carry features that match the pathway file."
            ),
        ) from exc

    if joint.shape[0] == 0 or joint.shape[1] == 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "No pathway scores could be computed. Check that the feature "
                "identifiers in these datasets match the pathway file."
            ),
        )

    n_clusters, labels = await run_in_threadpool(_cluster_fused, joint)
    # Each omics' share of the joint pathway space, by variance carried.
    widths = {
        name: int(np.asarray(getattr(s, "scores", s)).shape[1]) for name, s in per_omics.items()
    }
    blocks = {}
    start = 0
    for name, width in widths.items():
        blocks[name] = joint[:, start : start + width]
        start += width
    shares = DataFusion._variance_contributions(blocks)

    first = next(iter(omics_inputs.values()))
    return OmicsIntegrationResponse(
        method="pathway_integration",
        n_samples=int(joint.shape[0]),
        n_features=total_features,
        n_omics=len(omics_inputs),
        variance_explained=None,
        contribution_basis="pathway_score_variance",
        contributions=[
            OmicsContribution(
                dataset_id=by_key[key].id,
                dataset_name=by_key[key].name,
                omics_type=getattr(by_key[key].omics_type, "value", str(by_key[key].omics_type)),
                contribution=float(share),
            )
            for key, share in shares.items()
        ],
        n_clusters=n_clusters,
        embedding=[
            IntegrationSamplePoint(
                sample=sample,
                x=float(joint[i, 0]),
                y=float(joint[i, 1]) if joint.shape[1] > 1 else 0.0,
                cluster=labels[i],
            )
            for i, sample in enumerate(first.sample_names[: joint.shape[0]])
        ],
    )


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
                "Failed to read dataset %s at %s: %s",
                dataset.id,
                _for_log(dataset.storage_path),
                _for_log(exc),
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

    if body.method in _NETWORK_METHODS:
        return await _integrate_by_network(body, omics_inputs, by_key, total_features)

    if body.method in _PATHWAY_METHODS:
        return await _integrate_by_pathway(body, omics_inputs, by_key, total_features)

    model: DataFusion
    if body.method == "early_fusion":
        model = EarlyFusion(reduce_dim=body.n_components)
    else:
        model = IntermediateFusion(n_components=body.n_components)

    try:
        fusion = await run_in_threadpool(model.fit_transform, omics_inputs)
    except ValueError as exc:
        # _align_samples raises when the datasets share no sample identifiers.
        logger.info(
            "Integration rejected for project %s: %s",
            _for_log(body.project_id),
            _for_log(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Datasets could not be aligned. They must share sample identifiers "
                "in their row index."
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

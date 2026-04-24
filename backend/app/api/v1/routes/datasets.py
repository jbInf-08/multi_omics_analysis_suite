"""Dataset Routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.core.security import TokenPayload, get_current_user
from backend.app.models.dataset import Dataset, DatasetStatus, OmicsType
from backend.app.models.project import Project
from backend.app.schemas.common import PaginatedResponse
from backend.app.schemas.dataset import (
    DatasetCreate,
    DatasetResponse,
    DatasetSummary,
)

router = APIRouter()


@router.post("/", response_model=DatasetResponse, status_code=status.HTTP_201_CREATED)
async def create_dataset(
    dataset_data: DatasetCreate,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new dataset."""
    # Verify project access
    result = await db.execute(select(Project).where(Project.id == dataset_data.project_id))
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    if str(project.owner_id) != current_user.sub:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to add datasets to this project",
        )

    dataset = Dataset(
        name=dataset_data.name,
        description=dataset_data.description,
        omics_type=OmicsType(dataset_data.omics_type),
        data_format=dataset_data.data_format,
        source=dataset_data.source,
        source_id=dataset_data.source_id,
        metadata=dataset_data.metadata,
        clinical_data=dataset_data.clinical_data,
        sample_metadata=dataset_data.sample_metadata,
        project_id=dataset_data.project_id,
        status=DatasetStatus.UPLOADING,
    )

    db.add(dataset)
    await db.commit()
    await db.refresh(dataset)

    return dataset


@router.get("/", response_model=PaginatedResponse[DatasetSummary])
async def list_datasets(
    project_id: UUID | None = None,
    omics_type: str | None = None,
    status_filter: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List datasets."""
    # Build base query with project access check
    user_uuid = UUID(current_user.sub)
    query = select(Dataset).join(Project).where(Project.owner_id == user_uuid)
    count_query = select(func.count(Dataset.id)).join(Project).where(Project.owner_id == user_uuid)

    if project_id:
        query = query.where(Dataset.project_id == project_id)
        count_query = count_query.where(Dataset.project_id == project_id)

    if omics_type:
        query = query.where(Dataset.omics_type == omics_type)
        count_query = count_query.where(Dataset.omics_type == omics_type)

    if status_filter:
        query = query.where(Dataset.status == status_filter)
        count_query = count_query.where(Dataset.status == status_filter)

    # Count total
    count_result = await db.execute(count_query)
    total = count_result.scalar()

    # Get paginated results
    offset = (page - 1) * page_size
    result = await db.execute(
        query.order_by(Dataset.created_at.desc()).offset(offset).limit(page_size)
    )
    datasets = result.scalars().all()

    pages = (total + page_size - 1) // page_size if total > 0 else 1

    summaries = [
        DatasetSummary(
            id=d.id,
            name=d.name,
            omics_type=d.omics_type.value,
            status=d.status.value,
            sample_count=d.sample_count,
            feature_count=d.feature_count,
            source=d.source,
            created_at=d.created_at,
        )
        for d in datasets
    ]

    return PaginatedResponse(
        items=summaries,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
        has_next=page < pages,
        has_prev=page > 1,
    )


@router.get("/{dataset_id}", response_model=DatasetResponse)
async def get_dataset(
    dataset_id: UUID,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get dataset by ID."""
    result = await db.execute(
        select(Dataset)
        .join(Project)
        .where(Dataset.id == dataset_id)
        .where(Project.owner_id == UUID(current_user.sub))
    )
    dataset = result.scalar_one_or_none()

    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found or not authorized",
        )

    return dataset


@router.post("/{dataset_id}/upload")
async def upload_dataset_file(
    dataset_id: UUID,
    file: UploadFile = File(...),
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload data file for dataset."""
    import os
    from pathlib import Path

    import aiofiles

    # Verify dataset access
    result = await db.execute(
        select(Dataset)
        .join(Project)
        .where(Dataset.id == dataset_id)
        .where(Project.owner_id == UUID(current_user.sub))
    )
    dataset = result.scalar_one_or_none()

    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found or not authorized",
        )

    # Create storage directory
    upload_dir = Path(os.environ.get("UPLOAD_DIR", "./data/uploads"))
    dataset_dir = upload_dir / str(dataset_id)
    dataset_dir.mkdir(parents=True, exist_ok=True)

    # Save file
    file_path = dataset_dir / file.filename

    async with aiofiles.open(file_path, "wb") as f:
        content = await file.read()
        await f.write(content)

    # Determine file type
    file_ext = Path(file.filename).suffix.lower().lstrip(".")
    file_type_map = {
        "csv": "csv",
        "tsv": "tsv",
        "txt": "csv",
        "parquet": "parquet",
        "xlsx": "excel",
        "xls": "excel",
        "vcf": "vcf",
        "maf": "maf",
        "gct": "gct",
        "h5ad": "h5ad",
    }
    file_type = file_type_map.get(file_ext, "csv")

    # Update dataset status
    dataset.status = DatasetStatus.PROCESSING
    dataset.data_format = file_type
    await db.commit()

    # Start processing task
    from backend.app.tasks.data_tasks import process_uploaded_file

    task = process_uploaded_file.delay(
        dataset_id=str(dataset_id),
        file_path=str(file_path),
        file_type=file_type,
    )

    return {
        "message": "File uploaded successfully",
        "dataset_id": str(dataset_id),
        "filename": file.filename,
        "file_type": file_type,
        "task_id": task.id,
        "status": "processing",
    }


@router.post("/{dataset_id}/qc")
async def run_dataset_qc(
    dataset_id: UUID,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Run quality control on dataset."""
    result = await db.execute(
        select(Dataset)
        .join(Project)
        .where(Dataset.id == dataset_id)
        .where(Project.owner_id == UUID(current_user.sub))
    )
    dataset = result.scalar_one_or_none()

    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found or not authorized",
        )

    if dataset.status != DatasetStatus.READY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Dataset is not ready for QC (status: {dataset.status.value})",
        )

    # Start QC task
    from backend.app.tasks.data_tasks import run_quality_control

    task = run_quality_control.delay(
        dataset_id=str(dataset_id),
        parameters={},
    )

    return {
        "message": "Quality control started",
        "dataset_id": str(dataset_id),
        "task_id": task.id,
        "status": "running",
    }


@router.post("/{dataset_id}/normalize")
async def normalize_dataset(
    dataset_id: UUID,
    method: str = Query(default="zscore", description="Normalization method"),
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Normalize dataset."""
    result = await db.execute(
        select(Dataset)
        .join(Project)
        .where(Dataset.id == dataset_id)
        .where(Project.owner_id == UUID(current_user.sub))
    )
    dataset = result.scalar_one_or_none()

    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found or not authorized",
        )

    if dataset.status != DatasetStatus.READY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Dataset is not ready for normalization (status: {dataset.status.value})",
        )

    # Validate method
    valid_methods = ["zscore", "minmax", "quantile", "log2", "log10", "vst", "tmm", "tpm", "robust"]
    if method not in valid_methods:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid normalization method. Valid options: {valid_methods}",
        )

    # Start normalization task
    from backend.app.tasks.data_tasks import normalize_dataset as normalize_task

    task = normalize_task.delay(
        dataset_id=str(dataset_id),
        method=method,
    )

    return {
        "message": f"Normalization started with method: {method}",
        "dataset_id": str(dataset_id),
        "task_id": task.id,
        "method": method,
    }


@router.delete("/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dataset(
    dataset_id: UUID,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete dataset."""
    result = await db.execute(
        select(Dataset)
        .join(Project)
        .where(Dataset.id == dataset_id)
        .where(Project.owner_id == UUID(current_user.sub))
    )
    dataset = result.scalar_one_or_none()

    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found or not authorized",
        )

    dataset.status = DatasetStatus.ARCHIVED
    await db.commit()

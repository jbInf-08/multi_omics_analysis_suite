"""
Project Routes
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from backend.app.core.database import get_db
from backend.app.core.security import get_current_user, TokenPayload
from backend.app.models.project import Project, ProjectStatus
from backend.app.schemas.project import (
    ProjectCreate,
    ProjectUpdate,
    ProjectResponse,
    ProjectSummary,
)
from backend.app.schemas.common import PaginatedResponse


router = APIRouter()


@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_data: ProjectCreate,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new project."""
    project = Project(
        name=project_data.name,
        description=project_data.description,
        project_type=project_data.project_type,
        omics_types=project_data.omics_types,
        tags=project_data.tags,
        visibility=project_data.visibility,
        config=project_data.config,
        metadata=project_data.metadata,
        owner_id=UUID(current_user.sub),
    )
    
    db.add(project)
    await db.commit()
    await db.refresh(project)
    
    return project


@router.get("/", response_model=PaginatedResponse[ProjectSummary])
async def list_projects(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = None,
    omics_type: Optional[str] = None,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List user's projects."""
    # Build query
    user_uuid = UUID(current_user.sub)
    query = select(Project).where(Project.owner_id == user_uuid)
    count_query = select(func.count(Project.id)).where(Project.owner_id == user_uuid)
    
    if status_filter:
        query = query.where(Project.status == status_filter)
        count_query = count_query.where(Project.status == status_filter)
    
    if omics_type:
        query = query.where(Project.omics_types.contains([omics_type]))
        count_query = count_query.where(Project.omics_types.contains([omics_type]))
    
    # Count total
    count_result = await db.execute(count_query)
    total = count_result.scalar()
    
    # Get paginated results
    offset = (page - 1) * page_size
    result = await db.execute(
        query.order_by(Project.updated_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    projects = result.scalars().all()
    
    pages = (total + page_size - 1) // page_size if total > 0 else 1
    
    # Convert to summary
    summaries = [
        ProjectSummary(
            id=p.id,
            name=p.name,
            project_type=p.project_type,
            omics_types=p.omics_types,
            status=p.status.value,
            created_at=p.created_at,
        )
        for p in projects
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


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: UUID,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get project by ID."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    
    # Check access
    if str(project.owner_id) != current_user.sub and project.visibility == "private":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this project",
        )
    
    return project


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: UUID,
    project_update: ProjectUpdate,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update project."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    
    if str(project.owner_id) != current_user.sub:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this project",
        )
    
    # Update fields
    update_data = project_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "status":
            value = ProjectStatus(value)
        setattr(project, field, value)
    
    await db.commit()
    await db.refresh(project)
    
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: UUID,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete project (soft delete)."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    
    if str(project.owner_id) != current_user.sub:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this project",
        )
    
    project.status = ProjectStatus.DELETED
    await db.commit()

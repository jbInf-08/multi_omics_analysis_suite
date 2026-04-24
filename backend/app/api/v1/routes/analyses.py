"""
Analysis Routes
===============

API endpoints for creating, managing, and monitoring analyses.
"""

from typing import List, Optional
from uuid import UUID
import logging

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from backend.app.core.database import get_db
from backend.app.core.security import get_current_user, TokenPayload
from backend.app.core.celery_app import celery_app
from backend.app.models.analysis import Analysis, AnalysisResult, AnalysisStatus, AnalysisType
from backend.app.models.project import Project
from backend.app.schemas.analysis import (
    AnalysisCreate,
    AnalysisUpdate,
    AnalysisResponse,
    AnalysisResultResponse,
)
from backend.app.schemas.common import PaginatedResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/", response_model=AnalysisResponse, status_code=status.HTTP_201_CREATED)
async def create_analysis(
    analysis_data: AnalysisCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create and start a new analysis.
    
    The analysis will be queued for background processing via Celery.
    Use the WebSocket endpoint or poll the status endpoint to monitor progress.
    """
    # Verify project access
    result = await db.execute(select(Project).where(Project.id == analysis_data.project_id))
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
    
    # Create analysis record
    analysis = Analysis(
        name=analysis_data.name,
        description=analysis_data.description,
        analysis_type=AnalysisType(analysis_data.analysis_type),
        omics_types=analysis_data.omics_types,
        parameters=analysis_data.parameters,
        input_datasets=[str(d) for d in analysis_data.input_datasets],
        project_id=analysis_data.project_id,
        user_id=UUID(current_user.sub),
        status=AnalysisStatus.PENDING,
    )
    
    db.add(analysis)
    await db.commit()
    await db.refresh(analysis)
    
    # Start Celery task for analysis
    try:
        from backend.app.tasks.analysis_tasks import run_analysis
        
        task = run_analysis.apply_async(
            args=[str(analysis.id)],
            kwargs={"parameters": analysis_data.parameters},
            queue="analysis",
        )
        
        # Update analysis with task ID
        analysis.celery_task_id = task.id
        analysis.status = AnalysisStatus.QUEUED
        await db.commit()
        await db.refresh(analysis)
        
        logger.info(f"Analysis {analysis.id} queued with task {task.id}")
        
    except Exception as e:
        logger.error(f"Failed to queue analysis {analysis.id}: {e}")
        analysis.status = AnalysisStatus.FAILED
        analysis.error_message = f"Failed to queue task: {str(e)}"
        await db.commit()
        await db.refresh(analysis)
    
    return analysis


@router.get("/", response_model=PaginatedResponse[AnalysisResponse])
async def list_analyses(
    project_id: Optional[UUID] = None,
    status_filter: Optional[str] = None,
    analysis_type: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List analyses."""
    user_uuid = UUID(current_user.sub)
    query = select(Analysis).where(Analysis.user_id == user_uuid)
    count_query = select(func.count(Analysis.id)).where(Analysis.user_id == user_uuid)
    
    if project_id:
        query = query.where(Analysis.project_id == project_id)
        count_query = count_query.where(Analysis.project_id == project_id)
    
    if status_filter:
        query = query.where(Analysis.status == status_filter)
        count_query = count_query.where(Analysis.status == status_filter)
    
    if analysis_type:
        query = query.where(Analysis.analysis_type == analysis_type)
        count_query = count_query.where(Analysis.analysis_type == analysis_type)
    
    # Count total
    count_result = await db.execute(count_query)
    total = count_result.scalar()
    
    # Get paginated results
    offset = (page - 1) * page_size
    result = await db.execute(
        query.order_by(Analysis.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    analyses = result.scalars().all()
    
    pages = (total + page_size - 1) // page_size if total > 0 else 1
    
    return PaginatedResponse(
        items=analyses,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
        has_next=page < pages,
        has_prev=page > 1,
    )


@router.get("/{analysis_id}", response_model=AnalysisResponse)
async def get_analysis(
    analysis_id: UUID,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get analysis by ID."""
    result = await db.execute(
        select(Analysis)
        .where(Analysis.id == analysis_id)
        .where(Analysis.user_id == UUID(current_user.sub))
    )
    analysis = result.scalar_one_or_none()
    
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis not found",
        )
    
    return analysis


@router.get("/{analysis_id}/results", response_model=List[AnalysisResultResponse])
async def get_analysis_results(
    analysis_id: UUID,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get analysis results."""
    # Verify access
    result = await db.execute(
        select(Analysis)
        .where(Analysis.id == analysis_id)
        .where(Analysis.user_id == UUID(current_user.sub))
    )
    analysis = result.scalar_one_or_none()
    
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis not found",
        )
    
    # Get results
    result = await db.execute(
        select(AnalysisResult)
        .where(AnalysisResult.analysis_id == analysis_id)
        .order_by(AnalysisResult.created_at)
    )
    results = result.scalars().all()
    
    return results


@router.post("/{analysis_id}/cancel", response_model=AnalysisResponse)
async def cancel_analysis(
    analysis_id: UUID,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancel a running or queued analysis."""
    result = await db.execute(
        select(Analysis)
        .where(Analysis.id == analysis_id)
        .where(Analysis.user_id == UUID(current_user.sub))
    )
    analysis = result.scalar_one_or_none()
    
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis not found",
        )
    
    cancelable_statuses = [
        AnalysisStatus.PENDING,
        AnalysisStatus.QUEUED,
        AnalysisStatus.RUNNING,
    ]
    
    if analysis.status not in cancelable_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Analysis with status '{analysis.status}' cannot be cancelled",
        )
    
    # Cancel Celery task if running
    if analysis.celery_task_id:
        try:
            celery_app.control.revoke(
                analysis.celery_task_id,
                terminate=True,
                signal="SIGTERM"
            )
            logger.info(f"Cancelled Celery task {analysis.celery_task_id}")
        except Exception as e:
            logger.warning(f"Failed to revoke task {analysis.celery_task_id}: {e}")
    
    analysis.status = AnalysisStatus.CANCELLED
    await db.commit()
    await db.refresh(analysis)
    
    return analysis


@router.get("/{analysis_id}/status")
async def get_analysis_status(
    analysis_id: UUID,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get detailed status of an analysis including Celery task progress.
    
    Returns current status, progress percentage, and current step if running.
    """
    result = await db.execute(
        select(Analysis)
        .where(Analysis.id == analysis_id)
        .where(Analysis.user_id == UUID(current_user.sub))
    )
    analysis = result.scalar_one_or_none()
    
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis not found",
        )
    
    response = {
        "id": str(analysis.id),
        "status": analysis.status.value if hasattr(analysis.status, 'value') else analysis.status,
        "progress": 0.0,
        "current_step": None,
        "error_message": analysis.error_message if hasattr(analysis, 'error_message') else None,
    }
    
    # Get Celery task status if available
    if analysis.celery_task_id:
        try:
            from celery.result import AsyncResult
            task_result = AsyncResult(analysis.celery_task_id, app=celery_app)
            
            response["task_id"] = analysis.celery_task_id
            response["task_status"] = task_result.status
            
            if task_result.status == "PROGRESS" and task_result.info:
                response["progress"] = task_result.info.get("progress", 0.0)
                response["current_step"] = task_result.info.get("step")
            elif task_result.status == "SUCCESS":
                response["progress"] = 1.0
                response["result"] = task_result.result
            elif task_result.status == "FAILURE":
                response["error_message"] = str(task_result.result)
                
        except Exception as e:
            logger.warning(f"Failed to get task status: {e}")
    
    return response


@router.post("/{analysis_id}/retry", response_model=AnalysisResponse)
async def retry_analysis(
    analysis_id: UUID,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retry a failed analysis."""
    result = await db.execute(
        select(Analysis)
        .where(Analysis.id == analysis_id)
        .where(Analysis.user_id == UUID(current_user.sub))
    )
    analysis = result.scalar_one_or_none()
    
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis not found",
        )
    
    if analysis.status not in [AnalysisStatus.FAILED, AnalysisStatus.CANCELLED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only failed or cancelled analyses can be retried",
        )
    
    # Reset status and requeue
    analysis.status = AnalysisStatus.PENDING
    analysis.error_message = None
    await db.commit()
    
    # Start new Celery task
    try:
        from backend.app.tasks.analysis_tasks import run_analysis
        
        task = run_analysis.apply_async(
            args=[str(analysis.id)],
            kwargs={"parameters": analysis.parameters},
            queue="analysis",
        )
        
        analysis.celery_task_id = task.id
        analysis.status = AnalysisStatus.QUEUED
        await db.commit()
        await db.refresh(analysis)
        
        logger.info(f"Analysis {analysis.id} retried with task {task.id}")
        
    except Exception as e:
        logger.error(f"Failed to retry analysis {analysis.id}: {e}")
        analysis.status = AnalysisStatus.FAILED
        analysis.error_message = f"Failed to queue retry: {str(e)}"
        await db.commit()
        await db.refresh(analysis)
    
    return analysis


@router.delete("/{analysis_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_analysis(
    analysis_id: UUID,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete an analysis."""
    result = await db.execute(
        select(Analysis)
        .where(Analysis.id == analysis_id)
        .where(Analysis.user_id == UUID(current_user.sub))
    )
    analysis = result.scalar_one_or_none()
    
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis not found",
        )
    
    await db.delete(analysis)
    await db.commit()

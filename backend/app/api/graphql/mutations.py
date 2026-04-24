"""
GraphQL Mutations
=================

Database mutation resolvers for GraphQL.
"""

from typing import Optional, List
from uuid import UUID
from datetime import datetime, timezone
import strawberry
from strawberry.types import Info
from sqlalchemy import select, update, delete

from backend.app.api.graphql.types import (
    ProjectType,
    DatasetType,
    AnalysisType,
    ProjectInput,
    DatasetInput,
    AnalysisInput,
)
from backend.app.api.graphql.resolvers import (
    model_to_project_type,
    model_to_dataset_type,
    model_to_analysis_type,
)
from backend.app.core.database import get_async_session


def utc_now() -> datetime:
    """Return current UTC time."""
    return datetime.now(timezone.utc)


async def get_current_user_id(info: Info) -> UUID:
    """
    Extract current user ID from context.
    
    In a real implementation, this would get the user from the
    authentication context (e.g., JWT token).
    """
    # Try to get user from context
    if hasattr(info.context, "user") and info.context.user:
        return UUID(str(info.context.user.id))
    
    # For development, use a default user ID
    # In production, this should raise an authentication error
    import os
    default_user_id = os.environ.get("DEFAULT_USER_ID", "00000000-0000-0000-0000-000000000001")
    return UUID(default_user_id)


@strawberry.type
class Mutation:
    """GraphQL Mutation root."""
    
    @strawberry.mutation
    async def create_project(self, input: ProjectInput, info: Info) -> ProjectType:
        """Create a new project."""
        from backend.app.models.project import Project, ProjectStatus
        
        user_id = await get_current_user_id(info)
        
        async for session in get_async_session():
            try:
                project = Project(
                    name=input.name,
                    description=input.description,
                    project_type=input.project_type,
                    omics_types=input.omics_types,
                    tags=input.tags,
                    visibility=input.visibility,
                    status=ProjectStatus.ACTIVE,
                    owner_id=user_id,
                )
                
                session.add(project)
                await session.commit()
                await session.refresh(project)
                
                return model_to_project_type(project)
            except Exception as e:
                await session.rollback()
                raise Exception(f"Failed to create project: {str(e)}")
        
        raise Exception("Database session not available")
    
    @strawberry.mutation
    async def update_project(
        self,
        id: strawberry.ID,
        name: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        visibility: Optional[str] = None,
        status: Optional[str] = None,
    ) -> ProjectType:
        """Update a project."""
        from backend.app.models.project import Project, ProjectStatus
        
        async for session in get_async_session():
            try:
                result = await session.execute(
                    select(Project).where(Project.id == UUID(str(id)))
                )
                project = result.scalar_one_or_none()
                
                if not project:
                    raise Exception(f"Project {id} not found")
                
                if name is not None:
                    project.name = name
                if description is not None:
                    project.description = description
                if tags is not None:
                    project.tags = tags
                if visibility is not None:
                    project.visibility = visibility
                if status is not None:
                    try:
                        project.status = ProjectStatus(status)
                    except ValueError:
                        pass
                
                project.updated_at = utc_now()
                
                await session.commit()
                await session.refresh(project)
                
                return model_to_project_type(project)
            except Exception as e:
                await session.rollback()
                raise Exception(f"Failed to update project: {str(e)}")
        
        raise Exception("Database session not available")
    
    @strawberry.mutation
    async def delete_project(self, id: strawberry.ID) -> bool:
        """Delete a project (soft delete by setting status to DELETED)."""
        from backend.app.models.project import Project, ProjectStatus
        
        async for session in get_async_session():
            try:
                result = await session.execute(
                    select(Project).where(Project.id == UUID(str(id)))
                )
                project = result.scalar_one_or_none()
                
                if not project:
                    raise Exception(f"Project {id} not found")
                
                # Soft delete
                project.status = ProjectStatus.DELETED
                project.updated_at = utc_now()
                
                await session.commit()
                return True
            except Exception as e:
                await session.rollback()
                raise Exception(f"Failed to delete project: {str(e)}")
        
        return False
    
    @strawberry.mutation
    async def create_dataset(self, input: DatasetInput, info: Info) -> DatasetType:
        """Create a new dataset."""
        from backend.app.models.dataset import Dataset, DatasetStatus, OmicsType
        
        async for session in get_async_session():
            try:
                # Parse omics type
                try:
                    omics_type = OmicsType(input.omics_type)
                except ValueError:
                    omics_type = OmicsType.GENOMICS  # Default
                
                dataset = Dataset(
                    name=input.name,
                    description=input.description,
                    omics_type=omics_type,
                    data_format=input.data_format,
                    source=input.source,
                    status=DatasetStatus.UPLOADING,
                    project_id=UUID(str(input.project_id)),
                )
                
                session.add(dataset)
                await session.commit()
                await session.refresh(dataset)
                
                return model_to_dataset_type(dataset)
            except Exception as e:
                await session.rollback()
                raise Exception(f"Failed to create dataset: {str(e)}")
        
        raise Exception("Database session not available")
    
    @strawberry.mutation
    async def delete_dataset(self, id: strawberry.ID) -> bool:
        """Delete a dataset."""
        from backend.app.models.dataset import Dataset, DatasetStatus
        
        async for session in get_async_session():
            try:
                result = await session.execute(
                    select(Dataset).where(Dataset.id == UUID(str(id)))
                )
                dataset = result.scalar_one_or_none()
                
                if not dataset:
                    raise Exception(f"Dataset {id} not found")
                
                # Soft delete by setting status to ARCHIVED
                dataset.status = DatasetStatus.ARCHIVED
                dataset.updated_at = utc_now()
                
                await session.commit()
                return True
            except Exception as e:
                await session.rollback()
                raise Exception(f"Failed to delete dataset: {str(e)}")
        
        return False
    
    @strawberry.mutation
    async def create_analysis(self, input: AnalysisInput, info: Info) -> AnalysisType:
        """Create and start a new analysis."""
        from backend.app.models.analysis import Analysis, AnalysisStatus
        from backend.app.models.analysis import AnalysisType as AnalysisTypeEnum
        
        user_id = await get_current_user_id(info)
        
        async for session in get_async_session():
            try:
                # Parse analysis type
                try:
                    analysis_type = AnalysisTypeEnum(input.analysis_type)
                except ValueError:
                    analysis_type = AnalysisTypeEnum.SINGLE_OMICS
                
                analysis = Analysis(
                    name=input.name,
                    description=input.description,
                    analysis_type=analysis_type,
                    omics_types=input.omics_types,
                    parameters=input.parameters or {},
                    input_datasets=[str(d) for d in input.input_datasets],
                    status=AnalysisStatus.PENDING,
                    project_id=UUID(str(input.project_id)),
                    user_id=user_id,
                )
                
                session.add(analysis)
                await session.commit()
                await session.refresh(analysis)
                
                # Start the analysis task
                try:
                    from backend.app.tasks.analysis_tasks import run_analysis
                    task = run_analysis.delay(str(analysis.id), input.parameters)
                    
                    # Update with task ID
                    analysis.celery_task_id = task.id
                    analysis.status = AnalysisStatus.RUNNING
                    analysis.started_at = utc_now()
                    await session.commit()
                    await session.refresh(analysis)
                except Exception as task_error:
                    # Log but don't fail - analysis record is created
                    import logging
                    logging.warning(f"Failed to start analysis task: {task_error}")
                
                return model_to_analysis_type(analysis)
            except Exception as e:
                await session.rollback()
                raise Exception(f"Failed to create analysis: {str(e)}")
        
        raise Exception("Database session not available")
    
    @strawberry.mutation
    async def cancel_analysis(self, id: strawberry.ID) -> AnalysisType:
        """Cancel a running analysis."""
        from backend.app.models.analysis import Analysis, AnalysisStatus
        
        async for session in get_async_session():
            try:
                result = await session.execute(
                    select(Analysis).where(Analysis.id == UUID(str(id)))
                )
                analysis = result.scalar_one_or_none()
                
                if not analysis:
                    raise Exception(f"Analysis {id} not found")
                
                if analysis.status not in [AnalysisStatus.PENDING, AnalysisStatus.RUNNING]:
                    raise Exception(f"Analysis cannot be cancelled (status: {analysis.status.value})")
                
                # Cancel Celery task if running
                if analysis.celery_task_id:
                    try:
                        from backend.app.core.celery_app import celery_app
                        celery_app.control.revoke(analysis.celery_task_id, terminate=True)
                    except Exception as celery_error:
                        import logging
                        logging.warning(f"Failed to revoke Celery task: {celery_error}")
                
                # Update status
                analysis.status = AnalysisStatus.CANCELLED
                analysis.completed_at = utc_now()
                analysis.error_message = "Cancelled by user"
                
                await session.commit()
                await session.refresh(analysis)
                
                return model_to_analysis_type(analysis)
            except Exception as e:
                await session.rollback()
                raise Exception(f"Failed to cancel analysis: {str(e)}")
        
        raise Exception("Database session not available")

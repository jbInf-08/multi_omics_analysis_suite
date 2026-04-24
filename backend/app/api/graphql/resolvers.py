"""
GraphQL Resolvers
=================

Database query resolvers for GraphQL queries.
"""

from typing import List, Optional
from uuid import UUID
import strawberry
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.graphql.types import (
    UserType,
    ProjectType,
    DatasetType,
    AnalysisType,
    OmicsModuleType,
    PipelineType,
)
from backend.app.core.database import get_async_session


def model_to_user_type(user) -> UserType:
    """Convert User model to GraphQL type."""
    return UserType(
        id=strawberry.ID(str(user.id)),
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        organization=user.organization,
        is_active=user.is_active,
        is_verified=user.is_verified,
        roles=user.roles or [],
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


def model_to_project_type(project) -> ProjectType:
    """Convert Project model to GraphQL type."""
    return ProjectType(
        id=strawberry.ID(str(project.id)),
        name=project.name,
        description=project.description,
        project_type=project.project_type,
        omics_types=project.omics_types or [],
        status=project.status.value if hasattr(project.status, 'value') else str(project.status),
        visibility=project.visibility,
        tags=project.tags or [],
        owner_id=strawberry.ID(str(project.owner_id)),
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


def model_to_dataset_type(dataset) -> DatasetType:
    """Convert Dataset model to GraphQL type."""
    return DatasetType(
        id=strawberry.ID(str(dataset.id)),
        name=dataset.name,
        description=dataset.description,
        omics_type=dataset.omics_type.value if hasattr(dataset.omics_type, 'value') else str(dataset.omics_type),
        data_format=dataset.data_format,
        sample_count=dataset.sample_count,
        feature_count=dataset.feature_count,
        status=dataset.status.value if hasattr(dataset.status, 'value') else str(dataset.status),
        source=dataset.source,
        qc_passed=dataset.qc_passed,
        project_id=strawberry.ID(str(dataset.project_id)),
        created_at=dataset.created_at,
        updated_at=dataset.updated_at,
    )


def model_to_analysis_type(analysis) -> AnalysisType:
    """Convert Analysis model to GraphQL type."""
    return AnalysisType(
        id=strawberry.ID(str(analysis.id)),
        name=analysis.name,
        description=analysis.description,
        analysis_type=analysis.analysis_type.value if hasattr(analysis.analysis_type, 'value') else str(analysis.analysis_type),
        omics_types=analysis.omics_types or [],
        status=analysis.status.value if hasattr(analysis.status, 'value') else str(analysis.status),
        progress=analysis.progress or 0.0,
        current_step=analysis.current_step,
        total_steps=analysis.total_steps or 0,
        project_id=strawberry.ID(str(analysis.project_id)),
        user_id=strawberry.ID(str(analysis.user_id)),
        created_at=analysis.created_at,
        started_at=analysis.started_at,
        completed_at=analysis.completed_at,
    )


async def get_user(id: str) -> Optional[UserType]:
    """Get user by ID."""
    from backend.app.models.user import User
    
    async for session in get_async_session():
        try:
            result = await session.execute(
                select(User).where(User.id == UUID(id))
            )
            user = result.scalar_one_or_none()
            if user:
                return model_to_user_type(user)
        except Exception:
            pass
    return None


async def get_users(limit: int, offset: int) -> List[UserType]:
    """Get list of users."""
    from backend.app.models.user import User
    
    async for session in get_async_session():
        try:
            result = await session.execute(
                select(User)
                .order_by(User.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            users = result.scalars().all()
            return [model_to_user_type(u) for u in users]
        except Exception:
            pass
    return []


async def get_project(id: str) -> Optional[ProjectType]:
    """Get project by ID."""
    from backend.app.models.project import Project
    
    async for session in get_async_session():
        try:
            result = await session.execute(
                select(Project).where(Project.id == UUID(id))
            )
            project = result.scalar_one_or_none()
            if project:
                return model_to_project_type(project)
        except Exception:
            pass
    return None


async def get_projects(
    user_id: Optional[str],
    status: Optional[str],
    limit: int,
    offset: int,
) -> List[ProjectType]:
    """Get list of projects."""
    from backend.app.models.project import Project, ProjectStatus
    
    async for session in get_async_session():
        try:
            query = select(Project)
            
            if user_id:
                query = query.where(Project.owner_id == UUID(user_id))
            
            if status:
                try:
                    status_enum = ProjectStatus(status)
                    query = query.where(Project.status == status_enum)
                except ValueError:
                    pass
            
            query = query.order_by(Project.updated_at.desc()).limit(limit).offset(offset)
            
            result = await session.execute(query)
            projects = result.scalars().all()
            return [model_to_project_type(p) for p in projects]
        except Exception:
            pass
    return []


async def get_dataset(id: str) -> Optional[DatasetType]:
    """Get dataset by ID."""
    from backend.app.models.dataset import Dataset
    
    async for session in get_async_session():
        try:
            result = await session.execute(
                select(Dataset).where(Dataset.id == UUID(id))
            )
            dataset = result.scalar_one_or_none()
            if dataset:
                return model_to_dataset_type(dataset)
        except Exception:
            pass
    return None


async def get_datasets(
    project_id: Optional[str],
    omics_type: Optional[str],
    limit: int,
    offset: int,
) -> List[DatasetType]:
    """Get list of datasets."""
    from backend.app.models.dataset import Dataset, OmicsType
    
    async for session in get_async_session():
        try:
            query = select(Dataset)
            
            if project_id:
                query = query.where(Dataset.project_id == UUID(project_id))
            
            if omics_type:
                try:
                    omics_enum = OmicsType(omics_type)
                    query = query.where(Dataset.omics_type == omics_enum)
                except ValueError:
                    pass
            
            query = query.order_by(Dataset.updated_at.desc()).limit(limit).offset(offset)
            
            result = await session.execute(query)
            datasets = result.scalars().all()
            return [model_to_dataset_type(d) for d in datasets]
        except Exception:
            pass
    return []


async def get_analysis(id: str) -> Optional[AnalysisType]:
    """Get analysis by ID."""
    from backend.app.models.analysis import Analysis
    
    async for session in get_async_session():
        try:
            result = await session.execute(
                select(Analysis).where(Analysis.id == UUID(id))
            )
            analysis = result.scalar_one_or_none()
            if analysis:
                return model_to_analysis_type(analysis)
        except Exception:
            pass
    return None


async def get_analyses(
    project_id: Optional[str],
    status: Optional[str],
    limit: int,
    offset: int,
) -> List[AnalysisType]:
    """Get list of analyses."""
    from backend.app.models.analysis import Analysis, AnalysisStatus
    
    async for session in get_async_session():
        try:
            query = select(Analysis)
            
            if project_id:
                query = query.where(Analysis.project_id == UUID(project_id))
            
            if status:
                try:
                    status_enum = AnalysisStatus(status)
                    query = query.where(Analysis.status == status_enum)
                except ValueError:
                    pass
            
            query = query.order_by(Analysis.created_at.desc()).limit(limit).offset(offset)
            
            result = await session.execute(query)
            analyses = result.scalars().all()
            return [model_to_analysis_type(a) for a in analyses]
        except Exception:
            pass
    return []


async def get_omics_modules(
    category: Optional[str],
    active_only: bool,
) -> List[OmicsModuleType]:
    """Get list of omics modules from registry."""
    from backend.omics.base.registry import ModuleRegistry
    
    modules = []
    
    try:
        registered_modules = ModuleRegistry.list_modules()
        
        for module_info in registered_modules:
            if category and module_info.get("category") != category:
                continue
            if active_only and not module_info.get("is_active", True):
                continue
            
            modules.append(OmicsModuleType(
                name=module_info.get("name", ""),
                category=module_info.get("category", ""),
                description=module_info.get("description", ""),
                version=module_info.get("version", "1.0.0"),
                is_active=module_info.get("is_active", True),
                supported_formats=module_info.get("supported_formats", []),
                available_pipelines=module_info.get("available_pipelines", []),
                available_analyses=module_info.get("available_analyses", []),
            ))
    except Exception:
        # Return default modules if registry not available
        default_modules = [
            ("Genomics", "core", "Genomic data analysis including variant calling and CNV"),
            ("Transcriptomics", "core", "RNA-seq analysis and differential expression"),
            ("Proteomics", "core", "Protein quantification and PTM analysis"),
            ("Metabolomics", "core", "Metabolite profiling and pathway mapping"),
            ("Epigenomics", "specialized", "DNA methylation and chromatin analysis"),
            ("Pharmacogenomics", "specialized", "Drug response prediction"),
        ]
        
        for name, cat, desc in default_modules:
            if category and cat != category:
                continue
            modules.append(OmicsModuleType(
                name=name,
                category=cat,
                description=desc,
                version="1.0.0",
                is_active=True,
                supported_formats=["csv", "tsv", "parquet"],
                available_pipelines=[],
                available_analyses=[],
            ))
    
    return modules


async def get_pipelines(
    omics_type: Optional[str],
    limit: int,
    offset: int,
) -> List[PipelineType]:
    """Get list of pipelines."""
    from backend.app.models.pipeline import Pipeline
    
    async for session in get_async_session():
        try:
            query = select(Pipeline)
            
            if omics_type:
                # Filter by omics type in JSON array
                query = query.where(Pipeline.omics_types.contains([omics_type]))
            
            query = query.order_by(Pipeline.created_at.desc()).limit(limit).offset(offset)
            
            result = await session.execute(query)
            pipelines = result.scalars().all()
            
            return [
                PipelineType(
                    id=strawberry.ID(str(p.id)),
                    name=p.name,
                    description=p.description,
                    version=p.version,
                    omics_types=p.omics_types or [],
                    steps=p.steps or [],
                    is_active=p.is_active,
                    is_public=p.is_public,
                    created_at=p.created_at,
                )
                for p in pipelines
            ]
        except Exception:
            pass
    return []

"""API v1 Routes."""

from fastapi import APIRouter

from backend.app.api.v1.routes.analyses import router as analyses_router
from backend.app.api.v1.routes.auth import router as auth_router
from backend.app.api.v1.routes.bioinformatics_tools import router as bioinformatics_tools_router
from backend.app.api.v1.routes.datasets import router as datasets_router
from backend.app.api.v1.routes.ml import router as ml_router
from backend.app.api.v1.routes.omics import router as omics_router
from backend.app.api.v1.routes.pipelines import router as pipelines_router
from backend.app.api.v1.routes.projects import router as projects_router
from backend.app.api.v1.routes.users import router as users_router

api_router = APIRouter()

# Include all route modules
api_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
api_router.include_router(users_router, prefix="/users", tags=["Users"])
api_router.include_router(projects_router, prefix="/projects", tags=["Projects"])
api_router.include_router(datasets_router, prefix="/datasets", tags=["Datasets"])
api_router.include_router(analyses_router, prefix="/analyses", tags=["Analyses"])
api_router.include_router(omics_router, prefix="/omics", tags=["Omics Modules"])
api_router.include_router(pipelines_router, prefix="/pipelines", tags=["Pipelines"])
api_router.include_router(ml_router, prefix="/ml", tags=["Machine Learning"])
api_router.include_router(
    bioinformatics_tools_router,
    prefix="/tools",
    tags=["Bioinformatics Tools"],
)

"""Multi-Omics Analysis Suite - Main FastAPI Application.
=====================================================

Entry point for the FastAPI backend server.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from backend.app.api.graphql.context import AppGraphQLRouter, get_graphql_context
from backend.app.api.graphql.schema import schema
from backend.app.api.v1.routes import api_router
from backend.app.api.websocket.manager import websocket_router
from backend.app.core.config import settings
from backend.app.core.database import close_db, init_db
from backend.omics.base.registry import OmicsRegistry


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Application lifespan events."""
    # Startup
    print("Starting Multi-Omics Analysis Suite...")
    if settings.TOOLS_ALLOW_ANONYMOUS:
        print(
            "WARNING: TOOLS_ALLOW_ANONYMOUS=true enables unauthenticated /api/v1/tools access (local-dev only)."
        )
    await init_db()

    # Initialize omics registry
    registry = OmicsRegistry()
    await registry.discover_and_register_modules()
    app.state.omics_registry = registry

    print(f"Registered {len(registry.list_modules())} omics modules")
    print("Multi-Omics Analysis Suite started successfully!")

    yield

    # Shutdown
    print("Shutting down Multi-Omics Analysis Suite...")
    await close_db()
    print("Shutdown complete.")


# Create FastAPI application
app = FastAPI(
    title="Multi-Omics Analysis Suite",
    description="""
    A comprehensive multi-omics analysis platform covering 50+ omics disciplines.

    ## Features

    - **50+ Omics Types**: Genomics, Proteomics, Transcriptomics, Metabolomics, and many more
    - **Advanced ML/AI**: Deep learning, GNNs, AutoML, explainability
    - **Multi-Omics Integration**: Data fusion, pathway analysis, network integration
    - **Real-time Processing**: WebSocket updates, streaming analysis
    - **Production Ready**: Kubernetes, monitoring, security
    - **Bioinformatics tools** (`/api/v1/tools`): gene prediction (including optional Prodigal binary),
      MD, docking, structure→MD→dock; authenticate with JWT or `X-API-Key` when `TOOLS_API_KEY` is set

    ## API Versions

    - `/api/v1/` - REST API endpoints
    - `/api/v1/tools/` - Gene annotation, MD, docking (see OpenAPI **Bioinformatics Tools** tag)
    - `/graphql` - GraphQL API
    - `/ws/` - WebSocket connections
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)


# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler."""
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An internal error occurred",
            "type": type(exc).__name__,
            "message": str(exc) if settings.DEBUG else "Internal server error",
        },
    )


# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "service": "multi-omics-analysis-suite",
    }


# Readiness check endpoint
@app.get("/ready", tags=["Health"])
async def readiness_check(request: Request):
    """Readiness check endpoint."""
    registry = request.app.state.omics_registry
    return {
        "status": "ready",
        "omics_modules_loaded": len(registry.list_modules()),
        "categories": list(registry.list_categories()),
    }


# Include API routers
app.include_router(api_router, prefix="/api/v1")
app.include_router(websocket_router, prefix="/ws")

# GraphQL router
graphql_app = AppGraphQLRouter(schema, context_getter=get_graphql_context)
app.include_router(graphql_app, prefix="/graphql")


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Multi-Omics Analysis Suite",
        "version": "1.0.0",
        "description": "Comprehensive multi-omics analysis platform",
        "endpoints": {
            "api": "/api/v1",
            "docs": "/docs",
            "redoc": "/redoc",
            "graphql": "/graphql",
            "health": "/health",
            "websocket": "/ws",
        },
    }

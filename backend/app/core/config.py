"""
Application Configuration
=========================

Centralized configuration management using Pydantic Settings.
"""

from functools import lru_cache
from typing import List, Optional

from pydantic import field_validator, AnyHttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )
    
    # Application
    APP_NAME: str = "Multi-Omics Analysis Suite"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"
    
    # Security
    SECRET_KEY: str = "super-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"
    
    # Database - PostgreSQL
    DATABASE_URL: str = "postgresql+asyncpg://omics:omics_secret@localhost:5433/omics_db"
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_CACHE_TTL: int = 3600
    
    # Neo4j
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "neo4j_secret"
    
    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"
    
    # Kafka
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    
    # MinIO/S3
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minio_admin"
    MINIO_SECRET_KEY: str = "minio_secret"
    MINIO_BUCKET: str = "omics-data"
    MINIO_SECURE: bool = False
    
    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8050",
        "http://localhost:8000",
    ]
    
    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v
    
    # File Storage
    UPLOAD_DIR: str = "./data/uploads"
    RESULTS_DIR: str = "./results"
    MAX_UPLOAD_SIZE: int = 1024 * 1024 * 500  # 500 MB
    
    # ML/AI Settings
    ML_MODEL_DIR: str = "./models"
    ML_DEFAULT_DEVICE: str = "cpu"  # cpu, cuda, mps
    ML_MAX_WORKERS: int = 4
    
    # Analysis Settings
    DEFAULT_QC_THRESHOLD: float = 0.8
    DEFAULT_NORMALIZATION: str = "quantile"
    DEFAULT_BATCH_SIZE: int = 1000
    
    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_PERIOD: int = 60  # seconds

    # Bioinformatics tools API (/api/v1/tools)
    TOOLS_API_KEY: str = ""  # If set, same value in X-API-Key header authenticates tools routes
    TOOLS_ALLOW_ANONYMOUS: bool = False  # If true, tools routes accept requests with no auth (dangerous)
    TOOLS_CHEMISTRY_RATE_LIMIT: int = 30  # Max requests per client IP per window (0 = disabled)
    TOOLS_CHEMISTRY_RATE_PERIOD_SECONDS: int = 60
    # auto: use Redis when REDIS_URL is reachable; memory: in-process only; redis: require Redis
    TOOLS_CHEMISTRY_RATE_LIMIT_BACKEND: str = "auto"

    # Celery pipeline step outputs: spill large JSON to disk, keep summaries in DB
    PIPELINE_ARTIFACTS_DIR: str = "./data/pipeline_artifacts"
    PIPELINE_ARTIFACT_MAX_EMBED_BYTES: int = 95_000
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()

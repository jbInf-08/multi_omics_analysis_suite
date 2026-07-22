"""Pipeline and PipelineRun ORM models."""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship

from backend.app.core.database import Base


def utc_now() -> datetime:
    """Return the current timezone-aware UTC time."""
    return datetime.now(timezone.utc)


class PipelineStatus(str, enum.Enum):
    """Lifecycle state of a pipeline run."""

    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Pipeline(Base):
    """A reusable, versioned analysis pipeline definition."""

    __tablename__ = "pipelines"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    version = Column(String(50), nullable=False, default="1.0.0")
    pipeline_type = Column(String(100), nullable=True)
    omics_types = Column(JSONB, default=list, nullable=False)
    steps = Column(JSONB, default=list, nullable=False)
    default_parameters = Column(JSONB, default=dict, nullable=False)
    timeout_seconds = Column(Integer, nullable=True, default=3600)
    max_retries = Column(Integer, nullable=False, default=3)
    tags = Column(JSONB, default=list, nullable=False)
    author = Column(String(255), nullable=True)

    is_active = Column(Boolean, default=True, nullable=False)
    is_public = Column(Boolean, default=False, nullable=False)
    is_template = Column(Boolean, default=False, nullable=False)

    owner_id = Column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), default=utc_now)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=utc_now,
        onupdate=utc_now,
    )

    runs = relationship(
        "PipelineRun", back_populates="pipeline", cascade="all, delete-orphan", lazy="noload"
    )

    def __repr__(self) -> str:
        return f"<Pipeline id={self.id} name={self.name!r}>"


class PipelineRun(Base):
    """A single execution of a pipeline."""

    __tablename__ = "pipeline_runs"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pipeline_id = Column(
        PGUUID(as_uuid=True), ForeignKey("pipelines.id"), nullable=False, index=True
    )
    analysis_id = Column(PGUUID(as_uuid=True), ForeignKey("analyses.id"), nullable=True)

    status = Column(
        SAEnum(
            PipelineStatus,
            native_enum=False,
            length=50,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=PipelineStatus.PENDING,
    )
    parameters = Column(JSONB, default=dict, nullable=False)
    progress = Column(Float, default=0.0, nullable=False)
    current_step = Column(Integer, default=0, nullable=False)
    current_step_name = Column(String(255), nullable=True)
    step_results = Column(JSONB, default=list, nullable=False)
    error_message = Column(Text, nullable=True)
    error_step = Column(Integer, nullable=True)
    retry_count = Column(Integer, default=0, nullable=False)
    celery_task_id = Column(String(255), nullable=True)

    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), default=utc_now)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=utc_now,
        onupdate=utc_now,
    )

    pipeline = relationship("Pipeline", back_populates="runs", lazy="noload")

    def __repr__(self) -> str:
        return f"<PipelineRun id={self.id} pipeline_id={self.pipeline_id} status={self.status}>"

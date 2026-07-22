"""Analysis and AnalysisResult ORM models."""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import BigInteger, Column, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship

from backend.app.core.database import Base


def utc_now() -> datetime:
    """Return the current timezone-aware UTC time."""
    return datetime.now(timezone.utc)


class AnalysisStatus(str, enum.Enum):
    """Lifecycle state of an analysis run."""

    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AnalysisType(str, enum.Enum):
    """Kind of analysis being performed."""

    SINGLE_OMICS = "single_omics"
    MULTI_OMICS = "multi_omics"
    INTEGRATION = "integration"
    DIFFERENTIAL_EXPRESSION = "differential_expression"
    PATHWAY = "pathway"
    CLUSTERING = "clustering"
    SURVIVAL = "survival"


def _enum_column(enum_cls):
    """A non-native VARCHAR-backed enum that persists member values."""
    return SAEnum(
        enum_cls,
        native_enum=False,
        length=50,
        values_callable=lambda e: [m.value for m in e],
    )


class Analysis(Base):
    """A single analysis run against one or more datasets."""

    __tablename__ = "analyses"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    analysis_type = Column(_enum_column(AnalysisType), nullable=False)
    omics_types = Column(JSONB, default=list, nullable=False)
    status = Column(_enum_column(AnalysisStatus), nullable=False, default=AnalysisStatus.PENDING)

    progress = Column(Float, default=0.0, nullable=False)
    current_step = Column(String(255), nullable=True)
    total_steps = Column(Integer, default=0, nullable=False)

    parameters = Column(JSONB, default=dict, nullable=False)
    input_datasets = Column(JSONB, default=list, nullable=False)

    celery_task_id = Column(String(255), nullable=True)
    error_message = Column(Text, nullable=True)

    project_id = Column(PGUUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True)
    user_id = Column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), default=utc_now)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=utc_now,
        onupdate=utc_now,
    )

    project = relationship("Project", back_populates="analyses", lazy="noload")
    results = relationship(
        "AnalysisResult",
        back_populates="analysis",
        cascade="all, delete-orphan",
        lazy="noload",
    )

    def __repr__(self) -> str:
        return f"<Analysis id={self.id} name={self.name!r} status={self.status}>"


class AnalysisResult(Base):
    """A single result artifact produced by an analysis."""

    __tablename__ = "analysis_results"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("analyses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    result_type = Column(String(100), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    data = Column(JSONB, default=dict, nullable=False)
    summary = Column(JSONB, nullable=True)
    metrics = Column(JSONB, nullable=True)
    file_path = Column(String(500), nullable=True)
    file_type = Column(String(50), nullable=True)
    file_size = Column(BigInteger, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), default=utc_now)

    analysis = relationship("Analysis", back_populates="results", lazy="noload")

    def __repr__(self) -> str:
        return f"<AnalysisResult id={self.id} type={self.result_type!r}>"

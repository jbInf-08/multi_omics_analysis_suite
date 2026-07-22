"""Project ORM model."""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship

from backend.app.core.database import Base


def utc_now() -> datetime:
    """Return the current timezone-aware UTC time."""
    return datetime.now(timezone.utc)


class ProjectStatus(str, enum.Enum):
    """Lifecycle state of a project."""

    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class Project(Base):
    """A research project grouping datasets and analyses."""

    __tablename__ = "projects"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    project_type = Column(String(100), nullable=False, default="multi_omics")
    omics_types = Column(JSONB, default=list, nullable=False)
    tags = Column(JSONB, default=list, nullable=False)
    visibility = Column(String(50), nullable=False, default="private")
    status = Column(
        SAEnum(
            ProjectStatus,
            native_enum=False,
            length=50,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=ProjectStatus.ACTIVE,
    )
    config = Column(JSONB, default=dict, nullable=False)
    # ``metadata`` is reserved on the Declarative base, so the Python attribute is
    # ``project_metadata`` while the database column stays ``metadata``.
    project_metadata = Column("metadata", JSONB, default=dict, nullable=False)
    collaborators = Column(JSONB, default=list, nullable=False)

    owner_id = Column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    is_public = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), default=utc_now)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=utc_now,
        onupdate=utc_now,
    )

    datasets = relationship(
        "Dataset", back_populates="project", cascade="all, delete-orphan", lazy="noload"
    )
    analyses = relationship(
        "Analysis", back_populates="project", cascade="all, delete-orphan", lazy="noload"
    )

    def __init__(self, **kwargs):
        # Accept ``metadata=`` from callers even though the mapped attribute is
        # ``project_metadata`` (``metadata`` is reserved by Declarative).
        if "metadata" in kwargs:
            kwargs["project_metadata"] = kwargs.pop("metadata")
        super().__init__(**kwargs)

    def __repr__(self) -> str:
        return f"<Project id={self.id} name={self.name!r}>"

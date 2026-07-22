"""Dataset ORM model."""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship

from backend.app.core.database import Base


def utc_now() -> datetime:
    """Return the current timezone-aware UTC time."""
    return datetime.now(timezone.utc)


class OmicsType(str, enum.Enum):
    """Category of omics data held by a dataset."""

    GENOMICS = "genomics"
    TRANSCRIPTOMICS = "transcriptomics"
    PROTEOMICS = "proteomics"
    METABOLOMICS = "metabolomics"
    EPIGENOMICS = "epigenomics"
    PHARMACOGENOMICS = "pharmacogenomics"


class DatasetStatus(str, enum.Enum):
    """Processing lifecycle state of a dataset."""

    UPLOADING = "uploading"
    PROCESSING = "processing"
    READY = "ready"
    ARCHIVED = "archived"
    ERROR = "error"


def _enum_column(enum_cls):
    """A non-native VARCHAR-backed enum that persists member values."""
    return SAEnum(
        enum_cls,
        native_enum=False,
        length=50,
        values_callable=lambda e: [m.value for m in e],
    )


class Dataset(Base):
    """An uploaded omics dataset belonging to a project."""

    __tablename__ = "datasets"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    omics_type = Column(_enum_column(OmicsType), nullable=False, default=OmicsType.GENOMICS)
    data_format = Column(String(50), nullable=True)
    status = Column(_enum_column(DatasetStatus), nullable=False, default=DatasetStatus.UPLOADING)

    sample_count = Column(Integer, nullable=True)
    feature_count = Column(Integer, nullable=True)
    total_size = Column(BigInteger, nullable=True)

    source = Column(String(255), nullable=True)
    source_id = Column(String(255), nullable=True)

    qc_passed = Column(Boolean, nullable=True)
    qc_metrics = Column(JSONB, nullable=True)
    preprocessing_applied = Column(JSONB, default=list, nullable=False)
    normalization_method = Column(String(100), nullable=True)

    storage_path = Column(String(500), nullable=True)
    storage_type = Column(String(50), nullable=False, default="local")

    # ``metadata`` is reserved on the Declarative base; expose it as
    # ``dataset_metadata`` while keeping the database column named ``metadata``.
    dataset_metadata = Column("metadata", JSONB, default=dict, nullable=False)
    clinical_data = Column(JSONB, nullable=True)
    sample_metadata = Column(JSONB, nullable=True)

    project_id = Column(PGUUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True)
    uploaded_by = Column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), default=utc_now)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=utc_now,
        onupdate=utc_now,
    )

    project = relationship("Project", back_populates="datasets", lazy="noload")

    def __init__(self, **kwargs):
        # Accept ``metadata=`` from callers; the mapped attribute is
        # ``dataset_metadata`` because ``metadata`` is reserved by Declarative.
        if "metadata" in kwargs:
            kwargs["dataset_metadata"] = kwargs.pop("metadata")
        super().__init__(**kwargs)

    def __repr__(self) -> str:
        return f"<Dataset id={self.id} name={self.name!r}>"

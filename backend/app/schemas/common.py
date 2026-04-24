"""Common Pydantic Schemas."""

from datetime import datetime, timezone
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class BaseSchema(BaseModel):
    """Base schema with common configuration."""

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        use_enum_values=True,
    )


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated response wrapper."""

    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int
    has_next: bool
    has_prev: bool


class StatusResponse(BaseModel):
    """Status response."""

    status: str
    message: str
    timestamp: datetime = None

    def __init__(self, **data):
        if "timestamp" not in data:
            data["timestamp"] = datetime.now(timezone.utc)
        super().__init__(**data)


class ErrorResponse(BaseModel):
    """Error response."""

    detail: str
    error_code: str | None = None
    error_type: str | None = None
    timestamp: datetime = None

    def __init__(self, **data):
        if "timestamp" not in data:
            data["timestamp"] = datetime.now(timezone.utc)
        super().__init__(**data)


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
    service: str
    uptime: float | None = None
    components: dict | None = None


class TaskResponse(BaseModel):
    """Background task response."""

    task_id: str
    status: str
    progress: float = 0.0
    result: Any | None = None
    error: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None

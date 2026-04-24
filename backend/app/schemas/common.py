"""
Common Pydantic Schemas
"""

from typing import Generic, TypeVar, List, Optional, Any
from datetime import datetime, timezone
from uuid import UUID

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
    
    items: List[T]
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
    error_code: Optional[str] = None
    error_type: Optional[str] = None
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
    uptime: Optional[float] = None
    components: Optional[dict] = None


class TaskResponse(BaseModel):
    """Background task response."""
    
    task_id: str
    status: str
    progress: float = 0.0
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

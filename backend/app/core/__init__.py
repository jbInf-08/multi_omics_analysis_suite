"""Core application components."""

from backend.app.core.config import settings
from backend.app.core.database import close_db, get_db, init_db

__all__ = ["settings", "get_db", "init_db", "close_db"]

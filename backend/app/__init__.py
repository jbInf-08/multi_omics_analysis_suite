"""Multi-Omics Analysis Suite - FastAPI Application."""

from typing import Any

__all__ = ["app"]


def __getattr__(name: str) -> Any:
    if name == "app":
        from backend.app.main import app as _app

        globals()["app"] = _app
        return _app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

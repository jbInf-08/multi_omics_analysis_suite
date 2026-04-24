"""Tests for chemistry tools rate limiting."""

import pytest
from fastapi import HTTPException, status

from backend.app.core.config import settings
from backend.app.core.rate_limit import (
    MemorySlidingWindowLimiter,
    NoOpChemistryLimiter,
    get_chemistry_rate_limiter,
    reset_chemistry_rate_limiter,
)


@pytest.fixture(autouse=True)
def _reset_chemistry_limiter_singleton():
    reset_chemistry_rate_limiter()
    yield
    reset_chemistry_rate_limiter()


def test_memory_sliding_window_allows_then_429():
    lim = MemorySlidingWindowLimiter(2, 60.0)
    lim.check("ip1")
    lim.check("ip1")
    with pytest.raises(HTTPException) as exc:
        lim.check("ip1")
    assert exc.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS


def test_noop_limiter_never_429():
    lim = NoOpChemistryLimiter()
    for _ in range(100):
        lim.check("any")


def test_get_chemistry_rate_limiter_zero_limit_is_noop(monkeypatch):
    reset_chemistry_rate_limiter()
    monkeypatch.setattr(settings, "TOOLS_CHEMISTRY_RATE_LIMIT_BACKEND", "redis")
    lim = get_chemistry_rate_limiter(0, 60.0)
    assert isinstance(lim, NoOpChemistryLimiter)
    lim.check("any-key")


def test_get_chemistry_rate_limiter_memory_backend(monkeypatch):
    reset_chemistry_rate_limiter()
    monkeypatch.setattr(settings, "TOOLS_CHEMISTRY_RATE_LIMIT_BACKEND", "memory")
    monkeypatch.setattr(settings, "REDIS_URL", "redis://127.0.0.1:65530/0")
    lim = get_chemistry_rate_limiter(5, 60.0)
    assert isinstance(lim, MemorySlidingWindowLimiter)

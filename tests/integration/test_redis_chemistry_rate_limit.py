"""
Integration: Redis Lua sliding window for chemistry tools rate limit.

Requires a reachable ``REDIS_URL`` (GitHub Actions service, or ``docker compose up redis``).
"""

from __future__ import annotations

import os
import uuid

import pytest
from fastapi import HTTPException, status

from backend.app.core.config import settings
from backend.app.core.rate_limit import (
    RedisSlidingWindowLimiter,
    get_chemistry_rate_limiter,
    reset_chemistry_rate_limiter,
)


@pytest.fixture(autouse=True)
def _reset_chemistry_limiter_after_test():
    yield
    reset_chemistry_rate_limiter()


def _redis_ping(url: str) -> bool:
    try:
        import redis

        client = redis.from_url(url, decode_responses=True, socket_connect_timeout=2.0)
        client.ping()
        client.close()
        return True
    except Exception:
        return False


@pytest.fixture
def redis_url() -> str:
    url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    if not _redis_ping(url):
        pytest.skip(f"Redis not reachable at {url} (set REDIS_URL or start Redis)")
    return url


def test_chemistry_rate_limit_redis_lua_enforces_max(redis_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    reset_chemistry_rate_limiter()
    monkeypatch.setattr(settings, "TOOLS_CHEMISTRY_RATE_LIMIT_BACKEND", "redis", raising=False)
    monkeypatch.setattr(settings, "REDIS_URL", redis_url, raising=False)

    lim = get_chemistry_rate_limiter(2, 60.0)
    assert isinstance(lim, RedisSlidingWindowLimiter)

    key = f"itest-chem-rl-{uuid.uuid4().hex}"
    lim.check(key)
    lim.check(key)
    with pytest.raises(HTTPException) as exc:
        lim.check(key)
    assert exc.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS

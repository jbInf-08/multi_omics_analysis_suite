"""Rate limiting for CPU-heavy HTTP routes (chemistry tools).

- **memory**: single-process sliding window (default fallback).
- **redis**: atomic sliding window via Redis sorted set + Lua (shared across API replicas).
- **auto**: use Redis when ``REDIS_URL`` is reachable; otherwise memory.
"""

from __future__ import annotations

import logging
import time
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from threading import Lock

from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

_CHEMISTRY_LUA = """
local key = KEYS[1]
local cutoff = tonumber(ARGV[1])
local maxreq = tonumber(ARGV[2])
local score = tonumber(ARGV[3])
local member = ARGV[4]
local ttl = tonumber(ARGV[5])
redis.call('ZREMRANGEBYSCORE', key, 0, cutoff)
local c = redis.call('ZCARD', key)
if c >= maxreq then
  return 0
end
redis.call('ZADD', key, score, member)
redis.call('EXPIRE', key, ttl)
return 1
"""


class ChemistryRateLimiter(ABC):
    """Abstract per-key sliding window limiter."""

    @abstractmethod
    def check(self, key: str) -> None:
        """Raise HTTP 429 if ``key`` has exceeded the configured limit."""
        ...


class NoOpChemistryLimiter(ChemistryRateLimiter):
    def check(self, key: str) -> None:
        return None


class MemorySlidingWindowLimiter(ChemistryRateLimiter):
    """In-process sliding window (one replica only)."""

    def __init__(self, max_requests: int, period_seconds: float) -> None:
        self.max_requests = max_requests
        self.period = period_seconds
        self._hits: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def check(self, key: str) -> None:
        if self.max_requests <= 0:
            return
        now = time.monotonic()
        with self._lock:
            bucket = self._hits[key]
            cutoff = now - self.period
            bucket[:] = [t for t in bucket if t >= cutoff]
            if len(bucket) >= self.max_requests:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded for chemistry tools; retry later.",
                )
            bucket.append(now)


class RedisSlidingWindowLimiter(ChemistryRateLimiter):
    """Redis sorted-set + Lua (shared across workers / replicas)."""

    def __init__(
        self,
        max_requests: int,
        period_seconds: float,
        redis_url: str,
        key_prefix: str = "moas:tools:chemistry:rl",
    ) -> None:
        self.max_requests = max_requests
        self.period = float(period_seconds)
        self._url = redis_url
        self._prefix = key_prefix
        self._client = None
        self._script = None

    def _ensure(self):
        if self._client is None:
            import redis
            from redis.exceptions import RedisError

            try:
                self._client = redis.from_url(self._url, decode_responses=True)
                self._client.ping()
                self._script = self._client.register_script(_CHEMISTRY_LUA)
            except RedisError as e:
                logger.warning("Redis rate limiter unavailable (%s); falling back to memory", e)
                raise

    def check(self, key: str) -> None:
        if self.max_requests <= 0:
            return
        try:
            self._ensure()
        except Exception:
            _memory_fallback(self.max_requests, self.period).check(key)
            return

        rk = f"{self._prefix}:{key}"
        now = time.time()
        cutoff = now - self.period
        member = f"{now}:{uuid.uuid4().hex}"
        ttl = int(self.period) + 2
        try:
            ok = int(
                self._script(
                    keys=[rk],
                    args=[str(cutoff), str(self.max_requests), str(now), member, str(ttl)],
                )
            )
        except Exception as e:
            logger.warning("Redis rate limit check failed (%s); using memory limiter", e)
            _memory_fallback(self.max_requests, self.period).check(key)
            return

        if ok == 0:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded for chemistry tools; retry later.",
            )


_memory_fallback_cache: dict[tuple, MemorySlidingWindowLimiter] = {}
_memory_fb_lock = Lock()


def _memory_fallback(max_requests: int, period: float) -> MemorySlidingWindowLimiter:
    """Separate memory limiter per (max, period) for fallback path."""
    k = (max_requests, round(period, 6))
    with _memory_fb_lock:
        if k not in _memory_fallback_cache:
            _memory_fallback_cache[k] = MemorySlidingWindowLimiter(max_requests, period)
        return _memory_fallback_cache[k]


_chemistry_backend: ChemistryRateLimiter | None = None
_chemistry_lock = Lock()
_chemistry_sig: tuple | None = None


def reset_chemistry_rate_limiter() -> None:
    """Drop the cached limiter so the next :func:`get_chemistry_rate_limiter` rebuilds from settings (tests, reload)."""
    global _chemistry_backend, _chemistry_sig
    with _chemistry_lock:
        _chemistry_backend = None
        _chemistry_sig = None


def _build_backend(
    max_requests: int,
    period_seconds: float,
    backend: str,
    redis_url: str,
) -> ChemistryRateLimiter:
    if max_requests <= 0:
        return NoOpChemistryLimiter()

    mode = (backend or "auto").lower().strip()
    period_f = float(period_seconds)

    if mode == "memory":
        return MemorySlidingWindowLimiter(max_requests, period_f)

    if mode == "redis":
        return RedisSlidingWindowLimiter(max_requests, period_f, redis_url)

    # auto
    try:
        lim = RedisSlidingWindowLimiter(max_requests, period_f, redis_url)
        lim._ensure()
        return lim
    except Exception as e:
        logger.info("Chemistry rate limit using memory backend (auto): %s", e)
        return MemorySlidingWindowLimiter(max_requests, period_f)


def get_chemistry_rate_limiter(max_requests: int, period_seconds: float) -> ChemistryRateLimiter:
    """Singleton limiter for /tools/chemistry routes.

    Rebuilt when limit, period, backend mode, or Redis URL change (from settings).
    """
    global _chemistry_backend, _chemistry_sig
    from backend.app.core.config import settings

    sig = (
        max_requests,
        float(period_seconds),
        (settings.TOOLS_CHEMISTRY_RATE_LIMIT_BACKEND or "auto").lower(),
        str(settings.REDIS_URL),
    )
    with _chemistry_lock:
        if _chemistry_backend is None or _chemistry_sig != sig:
            _chemistry_backend = _build_backend(
                max_requests,
                period_seconds,
                settings.TOOLS_CHEMISTRY_RATE_LIMIT_BACKEND,
                settings.REDIS_URL,
            )
            _chemistry_sig = sig
        return _chemistry_backend

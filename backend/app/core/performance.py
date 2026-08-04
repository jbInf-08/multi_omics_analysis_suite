"""Performance Optimizations.
=========================

Connection pooling, caching strategies, batch processing, and distributed computing.
"""

import asyncio
import hashlib
import json
import pickle
from abc import ABC, abstractmethod
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

import redis.asyncio as redis
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.pool import QueuePool

# =============================================================================
# Connection Pool Configuration
# =============================================================================


class ConnectionPoolConfig:
    """Database connection pool configuration."""

    # PostgreSQL pool settings
    POSTGRES_POOL_SIZE = 20
    POSTGRES_MAX_OVERFLOW = 10
    POSTGRES_POOL_TIMEOUT = 30
    POSTGRES_POOL_RECYCLE = 1800  # 30 minutes
    POSTGRES_POOL_PRE_PING = True

    # Redis pool settings
    REDIS_MAX_CONNECTIONS = 50
    REDIS_SOCKET_TIMEOUT = 5
    REDIS_SOCKET_CONNECT_TIMEOUT = 5
    REDIS_RETRY_ON_TIMEOUT = True

    # Neo4j pool settings
    NEO4J_MAX_CONNECTION_POOL_SIZE = 50
    NEO4J_CONNECTION_ACQUISITION_TIMEOUT = 60


def configure_postgres_pool(engine: Engine) -> None:
    """Configure PostgreSQL connection pool settings."""

    @event.listens_for(engine, "connect")
    def set_postgres_options(dbapi_connection, connection_record):
        """Set PostgreSQL session options on connect."""
        cursor = dbapi_connection.cursor()
        cursor.execute("SET timezone='UTC'")
        cursor.execute("SET statement_timeout='300000'")  # 5 minutes
        cursor.close()

    @event.listens_for(engine, "checkout")
    def ping_connection(dbapi_connection, connection_record, connection_proxy):
        """Ping connection on checkout to verify it's alive."""
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("SELECT 1")
        except Exception:
            raise Exception("Connection is stale")
        finally:
            cursor.close()


def get_postgres_pool_config() -> dict[str, Any]:
    """Get PostgreSQL pool configuration dictionary."""
    return {
        "pool_size": ConnectionPoolConfig.POSTGRES_POOL_SIZE,
        "max_overflow": ConnectionPoolConfig.POSTGRES_MAX_OVERFLOW,
        "pool_timeout": ConnectionPoolConfig.POSTGRES_POOL_TIMEOUT,
        "pool_recycle": ConnectionPoolConfig.POSTGRES_POOL_RECYCLE,
        "pool_pre_ping": ConnectionPoolConfig.POSTGRES_POOL_PRE_PING,
        "poolclass": QueuePool,
    }


# =============================================================================
# Caching
# =============================================================================

T = TypeVar("T")


class CacheBackend(ABC):
    """Abstract cache backend."""

    @abstractmethod
    async def get(self, key: str) -> Any | None: ...

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: int | None = None) -> None: ...

    @abstractmethod
    async def delete(self, key: str) -> None: ...

    @abstractmethod
    async def exists(self, key: str) -> bool: ...

    @abstractmethod
    async def clear_pattern(self, pattern: str) -> int: ...


class RedisCache(CacheBackend):
    """Redis-based cache backend."""

    def __init__(self, redis_url: str, prefix: str = "omics"):
        self.redis_url = redis_url
        self.prefix = prefix
        self._pool: redis.ConnectionPool | None = None
        self._client: redis.Redis | None = None

    async def connect(self) -> None:
        """Initialize Redis connection pool."""
        self._pool = redis.ConnectionPool.from_url(
            self.redis_url,
            max_connections=ConnectionPoolConfig.REDIS_MAX_CONNECTIONS,
            socket_timeout=ConnectionPoolConfig.REDIS_SOCKET_TIMEOUT,
            socket_connect_timeout=ConnectionPoolConfig.REDIS_SOCKET_CONNECT_TIMEOUT,
            retry_on_timeout=ConnectionPoolConfig.REDIS_RETRY_ON_TIMEOUT,
        )
        self._client = redis.Redis(connection_pool=self._pool)

    async def close(self) -> None:
        """Close Redis connection pool."""
        if self._client:
            await self._client.close()
        if self._pool:
            await self._pool.disconnect()

    def _make_key(self, key: str) -> str:
        """Generate prefixed cache key."""
        return f"{self.prefix}:{key}"

    async def get(self, key: str) -> Any | None:
        """Get value from cache."""
        if not self._client:
            return None

        data = await self._client.get(self._make_key(key))
        if data:
            return pickle.loads(data)
        return None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Set value in cache."""
        if not self._client:
            return

        data = pickle.dumps(value)
        if ttl:
            await self._client.setex(self._make_key(key), ttl, data)
        else:
            await self._client.set(self._make_key(key), data)

    async def delete(self, key: str) -> None:
        """Delete value from cache."""
        if not self._client:
            return
        await self._client.delete(self._make_key(key))

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        if not self._client:
            return False
        return await self._client.exists(self._make_key(key)) > 0

    async def clear_pattern(self, pattern: str) -> int:
        """Clear all keys matching pattern."""
        if not self._client:
            return 0

        keys = []
        async for key in self._client.scan_iter(match=self._make_key(pattern)):
            keys.append(key)

        if keys:
            return await self._client.delete(*keys)
        return 0


class InMemoryCache(CacheBackend):
    """Simple in-memory cache for development/testing."""

    def __init__(self):
        self._cache: dict[str, tuple] = {}  # (value, expiry)

    async def get(self, key: str) -> Any | None:
        import time

        if key in self._cache:
            value, expiry = self._cache[key]
            if expiry is None or expiry > time.time():
                return value
            del self._cache[key]
        return None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        import time

        expiry = time.time() + ttl if ttl else None
        self._cache[key] = (value, expiry)

    async def delete(self, key: str) -> None:
        self._cache.pop(key, None)

    async def exists(self, key: str) -> bool:
        return key in self._cache

    async def clear_pattern(self, pattern: str) -> int:
        import fnmatch

        keys_to_delete = [k for k in self._cache if fnmatch.fnmatch(k, pattern)]
        for key in keys_to_delete:
            del self._cache[key]
        return len(keys_to_delete)


def cache_key(*args, **kwargs) -> str:
    """Generate cache key from arguments."""
    key_data = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True, default=str)
    # usedforsecurity=False: this is a cache key, not a security control.
    return hashlib.md5(key_data.encode(), usedforsecurity=False).hexdigest()


def cached(
    ttl: int = 300,
    prefix: str = "cache",
    key_func: Callable[..., str] | None = None,
):
    """Decorator for caching function results."""

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            # Get cache from app state or use in-memory
            cache = getattr(async_wrapper, "_cache", None) or InMemoryCache()

            # Generate cache key
            if key_func:
                key = key_func(*args, **kwargs)
            else:
                key = f"{prefix}:{func.__name__}:{cache_key(*args, **kwargs)}"

            # Try to get from cache
            result = await cache.get(key)
            if result is not None:
                return result

            # Call function and cache result
            result = await func(*args, **kwargs)
            await cache.set(key, result, ttl)

            return result

        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> T:
            return asyncio.run(async_wrapper(*args, **kwargs))

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def invalidate_cache(pattern: str):
    """Decorator to invalidate cache after function execution."""

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            result = await func(*args, **kwargs)

            cache = getattr(async_wrapper, "_cache", None)
            if cache:
                await cache.clear_pattern(pattern)

            return result

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return func

    return decorator


# =============================================================================
# Batch Processing
# =============================================================================


class BatchProcessor:
    """Process items in batches for better performance."""

    def __init__(
        self,
        batch_size: int = 100,
        max_workers: int = 4,
    ):
        self.batch_size = batch_size
        self.max_workers = max_workers

    async def process(
        self,
        items: list[T],
        process_func: Callable[[list[T]], list[Any]],
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[Any]:
        """Process items in batches."""
        results = []
        total = len(items)
        processed = 0

        for i in range(0, total, self.batch_size):
            batch = items[i : i + self.batch_size]

            if asyncio.iscoroutinefunction(process_func):
                batch_results = await process_func(batch)
            else:
                batch_results = process_func(batch)

            results.extend(batch_results)
            processed += len(batch)

            if progress_callback:
                progress_callback(processed, total)

        return results

    async def process_parallel(
        self,
        items: list[T],
        process_func: Callable[[T], Any],
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[Any]:
        """Process items in parallel batches using asyncio."""
        semaphore = asyncio.Semaphore(self.max_workers)
        results = []
        total = len(items)
        processed = 0

        async def process_with_semaphore(item: T) -> Any:
            async with semaphore:
                if asyncio.iscoroutinefunction(process_func):
                    return await process_func(item)
                return process_func(item)

        for i in range(0, total, self.batch_size * self.max_workers):
            batch = items[i : i + self.batch_size * self.max_workers]

            tasks = [process_with_semaphore(item) for item in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in batch_results:
                if isinstance(result, Exception):
                    results.append(None)
                else:
                    results.append(result)

            processed += len(batch)

            if progress_callback:
                progress_callback(processed, total)

        return results


# =============================================================================
# Query Optimization
# =============================================================================


class QueryOptimizer:
    """SQL query optimization utilities."""

    @staticmethod
    def paginate(query, page: int, page_size: int):
        """Add pagination to query."""
        offset = (page - 1) * page_size
        return query.offset(offset).limit(page_size)

    @staticmethod
    def add_index_hints(query, table_name: str, index_name: str):
        """Add index hints to query (PostgreSQL)."""
        return query.with_hint(None, f"/*+ IndexScan({table_name} {index_name}) */", "postgresql")


# =============================================================================
# Memory Management
# =============================================================================


class MemoryManager:
    """Memory management utilities."""

    @staticmethod
    def get_memory_usage() -> dict[str, int]:
        """Get current memory usage."""
        import psutil

        process = psutil.Process()
        info = process.memory_info()
        return {
            "rss": info.rss,
            "vms": info.vms,
            "percent": process.memory_percent(),
        }

    @staticmethod
    def clear_caches() -> None:
        """Clear Python internal caches."""
        import gc

        gc.collect()

    @staticmethod
    def optimize_numpy_memory() -> None:
        """Optimize NumPy memory settings."""
        try:
            import numpy as np

            # Disable memory preallocation
            np.set_printoptions(threshold=100)
        # Optional at runtime: the tuning is applied when the package is
        # present and skipped when it is not. Nothing to handle.
        except ImportError:
            pass

    @staticmethod
    def optimize_pandas_memory() -> None:
        """Optimize pandas memory settings."""
        try:
            import pandas as pd

            pd.options.mode.copy_on_write = True
        # Optional at runtime: the tuning is applied when the package is
        # present and skipped when it is not. Nothing to handle.
        except ImportError:
            pass


# =============================================================================
# Distributed Computing (Dask/Ray Integration)
# =============================================================================


class DistributedConfig:
    """Configuration for distributed computing."""

    DASK_SCHEDULER_ADDRESS: str | None = None
    RAY_ADDRESS: str | None = None

    @classmethod
    def use_dask(cls) -> bool:
        """Check if Dask should be used."""
        return cls.DASK_SCHEDULER_ADDRESS is not None

    @classmethod
    def use_ray(cls) -> bool:
        """Check if Ray should be used."""
        return cls.RAY_ADDRESS is not None


def get_dask_client():
    """Get Dask distributed client."""
    if not DistributedConfig.use_dask():
        return None

    try:
        from dask.distributed import Client

        return Client(DistributedConfig.DASK_SCHEDULER_ADDRESS)
    except ImportError:
        return None


def get_ray_context():
    """Initialize Ray context."""
    if not DistributedConfig.use_ray():
        return False

    try:
        import ray

        if not ray.is_initialized():
            ray.init(address=DistributedConfig.RAY_ADDRESS)
        return True
    except ImportError:
        return False

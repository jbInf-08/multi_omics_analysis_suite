"""
Database Configuration
======================

Async database connections for PostgreSQL, Redis, and Neo4j.
"""

from typing import AsyncGenerator, Optional
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool
import redis.asyncio as redis
from neo4j import AsyncGraphDatabase, AsyncDriver

from backend.app.core.config import settings


# SQLAlchemy Base
Base = declarative_base()

# Global instances
_engine: Optional[AsyncEngine] = None
_async_session_factory: Optional[async_sessionmaker] = None
_redis_client: Optional[redis.Redis] = None
_neo4j_driver: Optional[AsyncDriver] = None


async def init_db() -> None:
    """Initialize all database connections."""
    global _engine, _async_session_factory, _redis_client, _neo4j_driver
    
    # PostgreSQL
    _engine = create_async_engine(
        settings.DATABASE_URL,
        pool_size=settings.DATABASE_POOL_SIZE,
        max_overflow=settings.DATABASE_MAX_OVERFLOW,
        echo=settings.DEBUG,
        future=True,
    )
    
    _async_session_factory = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )
    
    # Create tables
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Redis
    _redis_client = redis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
    )
    
    # Neo4j
    _neo4j_driver = AsyncGraphDatabase.driver(
        settings.NEO4J_URI,
        auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
    )


async def close_db() -> None:
    """Close all database connections."""
    global _engine, _redis_client, _neo4j_driver
    
    if _engine:
        await _engine.dispose()
    
    if _redis_client:
        await _redis_client.close()
    
    if _neo4j_driver:
        await _neo4j_driver.close()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get async database session."""
    if _async_session_factory is None:
        raise RuntimeError("Database not initialized")
    
    async with _async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def get_async_session():
    """
    Async generator of database sessions for GraphQL resolvers/mutations.
    Yields a single session per call; use with: async for session in get_async_session()
    """
    async def _gen():
        if _async_session_factory is None:
            return
        async with _async_session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    return _gen()


def get_redis() -> redis.Redis:
    """Get Redis client."""
    if _redis_client is None:
        raise RuntimeError("Redis not initialized")
    return _redis_client


def get_neo4j() -> AsyncDriver:
    """Get Neo4j driver."""
    if _neo4j_driver is None:
        raise RuntimeError("Neo4j not initialized")
    return _neo4j_driver


@asynccontextmanager
async def get_neo4j_session():
    """Get Neo4j session context manager."""
    driver = get_neo4j()
    session = driver.session()
    try:
        yield session
    finally:
        await session.close()

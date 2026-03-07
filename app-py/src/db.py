"""Database connection pool and SQLAlchemy engine. Uses central config for connection parameters."""

from typing import Optional

import asyncpg
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from .config import (
    POSTGRES_HOST,
    POSTGRES_PORT,
    POSTGRES_USER,
    POSTGRES_PASSWORD,
    POSTGRES_DB,
)

_pool: Optional[asyncpg.Pool] = None
_engine: Optional[AsyncEngine] = None


def _get_config() -> dict:
    return {
        "host": POSTGRES_HOST,
        "port": POSTGRES_PORT,
        "user": POSTGRES_USER,
        "password": POSTGRES_PASSWORD,
        "database": POSTGRES_DB,
    }


def _database_url_async() -> str:
    """PostgreSQL URL for async driver (asyncpg)."""
    c = _get_config()
    return (
        f"postgresql+asyncpg://{c['user']}:{c['password']}@{c['host']}:{c['port']}/{c['database']}"
    )


async def get_pool() -> asyncpg.Pool:
    """Get or create the database connection pool."""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(**_get_config())
    return _pool


async def close_pool() -> None:
    """Close the database connection pool."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def get_engine() -> AsyncEngine:
    """Get or create the SQLAlchemy async engine (for ORM repositories)."""
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            _database_url_async(),
            pool_pre_ping=True,
        )
    return _engine


async def close_engine() -> None:
    """Dispose the SQLAlchemy async engine."""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None

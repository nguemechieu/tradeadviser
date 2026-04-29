from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any, AsyncContextManager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from server.app.backend.db import Base

# ============================================================
# Database URL
# ============================================================

DEFAULT_DATABASE_URL = "sqlite+aiosqlite:///./tradeadviser.db"

RAW_DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)


def normalize_database_url(url: str) -> str:
    """
    Normalize database URLs for async SQLAlchemy.

    Examples:
        postgresql://user:pass@localhost/db
            -> postgresql+asyncpg://user:pass@localhost/db

        postgres://user:pass@localhost/db
            -> postgresql+asyncpg://user:pass@localhost/db

        sqlite:///./app.db
            -> sqlite+aiosqlite:///./app.db
    """

    clean_url = url.strip()

    if clean_url.startswith("postgresql://"):
        return clean_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    if clean_url.startswith("postgres://"):
        return clean_url.replace("postgres://", "postgresql+asyncpg://", 1)

    if clean_url.startswith("sqlite:///"):
        return clean_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)

    return clean_url


DATABASE_URL = normalize_database_url(RAW_DATABASE_URL)


def _is_sqlite(url: str) -> bool:
    return url.startswith("sqlite+aiosqlite")


# ============================================================
# Engine
# ============================================================

engine_kwargs: dict[str, Any] = {
    "echo": os.getenv("SQL_ECHO", "0").lower() in {"1", "true", "yes"},
    "future": True,
}

if _is_sqlite(DATABASE_URL):
    # SQLite does not support normal Postgres-style pool options.
    pass
else:
    engine_kwargs.update(
        {
            "pool_pre_ping": True,
            "pool_size": int(os.getenv("DB_POOL_SIZE", "5")),
            "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "10")),
            "pool_timeout": int(os.getenv("DB_POOL_TIMEOUT", "30")),
            "pool_recycle": int(os.getenv("DB_POOL_RECYCLE", "1800")),
        }
    )


engine: AsyncEngine = create_async_engine(
    DATABASE_URL,
    **engine_kwargs,
)


# ============================================================
# Session Factory
# ============================================================

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


# ============================================================
# FastAPI Dependency
# ============================================================

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI database dependency.

    Usage:
        async def route(db: AsyncSession = Depends(get_db)):
            ...
    """

    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ============================================================
# Manual Session Context
# ============================================================

@asynccontextmanager
async def session_scope() -> AsyncGenerator[AsyncSession, None]:
    """
    Manual session context manager.

    Useful for:
    - background workers
    - scripts
    - tests
    - startup tasks

    Usage:
        async with session_scope() as db:
            ...
    """

    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ============================================================
# Database Lifecycle
# ============================================================

async def init_db() -> None:
    """
    Create all database tables.

    Good for local development.
    For production, use Alembic migrations instead.
    """

    context: AsyncContextManager[AsyncConnection] = engine.begin()

    async with context as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_db() -> None:
    """
    Drop all database tables.

    Dangerous.
    Use only for local development or tests.
    """

    context: AsyncContextManager[AsyncConnection] = engine.begin()

    async with context as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def close_db() -> None:
    """
    Dispose the database engine.

    Call this during FastAPI shutdown.
    """

    await engine.dispose()


# ============================================================
# Health Check
# ============================================================

async def ping_database() -> bool:
    """
    Check if the database is reachable.
    """

    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def database_status() -> dict[str, Any]:
    """
    Return database health metadata.
    """

    healthy = await ping_database()

    return {
        "database": "ok" if healthy else "error",
        "connected": healthy,
        "driver": DATABASE_URL.split("://", 1)[0],
        "sqlite": _is_sqlite(DATABASE_URL),
    }
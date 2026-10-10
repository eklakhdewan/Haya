"""Async SQLAlchemy infrastructure for persistent security state."""
from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from orchestrator.core.config import Environment, get_settings


@dataclass(frozen=True)
class DatabaseRuntime:
    """Owns the engine and session factory for one application process."""

    engine: AsyncEngine
    sessions: async_sessionmaker[AsyncSession]

    async def dispose(self) -> None:
        """Close pooled database connections during application shutdown."""
        await self.engine.dispose()


def normalize_async_database_url(database_url: str) -> str:
    """Normalize PostgreSQL URLs for the asyncpg SQLAlchemy driver."""
    url = database_url.strip()
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql+asyncpg://"):
        return url
    raise ValueError("DATABASE_URL must use a PostgreSQL URL supported by asyncpg.")


def create_database_runtime(database_url: str | None = None) -> DatabaseRuntime | None:
    """Create database resources, requiring them in production.

    Development and test environments may intentionally use the in-memory device
    manager. Production never silently falls back when persistent storage is absent.
    """
    settings = get_settings()
    configured_url = settings.database_url if database_url is None else database_url

    if not configured_url.strip():
        if settings.environment == Environment.PRODUCTION:
            raise RuntimeError("Production requires DATABASE_URL for persistent security state.")
        return None

    url = normalize_async_database_url(configured_url)
    engine = create_async_engine(
        url,
        pool_pre_ping=True,
        pool_recycle=1800,
    )
    sessions = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    return DatabaseRuntime(engine=engine, sessions=sessions)


async def get_session(runtime: DatabaseRuntime) -> AsyncIterator[AsyncSession]:
    """Yield a scoped async session; transaction boundaries belong to the caller."""
    async with runtime.sessions() as session:
        yield session

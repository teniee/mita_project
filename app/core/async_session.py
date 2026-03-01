"""
Async Database Session Management for MITA
Provides async SQLAlchemy session handling with proper connection management and monitoring
"""

import logging
from typing import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import StaticPool
from sqlalchemy import text

from app.core.config import settings

logger = logging.getLogger(__name__)

# Database engine and session - initialized lazily
async_engine = None
AsyncSessionLocal = None


def _normalize_database_url(url: str) -> str:
    """
    Convert any postgres URL into correct asyncpg format.
    Always enforce asyncpg + SSL + statement cache off for PgBouncer.
    """
    url = url.strip()

    # convert postgres:// → postgresql+asyncpg://
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)

    if url.startswith("postgresql://") and "+asyncpg" not in url:
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)

    # enforce SSL (required by Supabase)
    if "sslmode=" in url:
        url = url.replace("sslmode=", "ssl=")

    if "ssl=" not in url:
        sep = "&" if "?" in url else "?"
        url += f"{sep}ssl=require"

    # Remove statement_cache_size from URL if present (will be set in connect_args)
    if "statement_cache_size=" in url:
        import re
        url = re.sub(r'[&?]statement_cache_size=\d+', '', url)

    return url


def initialize_database() -> None:
    """Initialize database engine and session factory"""
    global async_engine, AsyncSessionLocal

    if async_engine is not None:
        return  # already initialized

    if not settings.DATABASE_URL:
        logger.error("DATABASE_URL is required but not set")
        raise ValueError("DATABASE_URL is required but not set")

    # normalize raw URL
    database_url = _normalize_database_url(settings.DATABASE_URL)
    logger.info(f"Final database URL used by asyncpg: {database_url}")

    try:
        engine_kwargs = {
            "echo": False,
            "pool_pre_ping": True,

            # safe pool settings for Render + Supabase pooler
            "pool_size": 5,
            "max_overflow": 10,
            "pool_timeout": 30,
            "pool_recycle": 1800,

            # CRITICAL: Disable server-side prepared statements for PgBouncer transaction mode
            "pool_use_lifo": True,  # Use LIFO for better connection reuse
        }

        # SQLite fallback
        if "sqlite" in database_url:
            engine_kwargs["poolclass"] = StaticPool

        # Prepare connection arguments with correct types for asyncpg
        # CRITICAL for PgBouncer transaction mode
        connect_args = {
            "statement_cache_size": 0,  # Disable client-side statement cache
            "prepared_statement_cache_size": 0,  # Disable prepared statements completely
            "server_settings": {
                "jit": "off",  # Disable JIT compilation for better compatibility
            },
        }

        async_engine_local = create_async_engine(
            database_url,
            connect_args=connect_args,
            **engine_kwargs,
        )

        AsyncSessionLocal = async_sessionmaker(
            bind=async_engine_local,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )

        globals()["async_engine"] = async_engine_local
        logger.info("Database engine initialized successfully")

    except Exception as e:
        logger.error(f"Failed to create database engine: {type(e).__name__}: {e}")
        raise


# Base class for all models
Base = declarative_base()


def get_async_session_factory():
    """Get the async session factory for direct session creation"""
    initialize_database()

    if AsyncSessionLocal is None:
        raise RuntimeError("Database not properly initialized")

    return AsyncSessionLocal


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """Async database dependency for FastAPI"""
    initialize_database()

    if AsyncSessionLocal is None:
        raise RuntimeError("Database not properly initialized")

    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_async_db_context():
    """Context manager for async database operations"""
    initialize_database()

    if AsyncSessionLocal is None:
        raise RuntimeError("Database not properly initialized")

    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# Legacy compatibility functions
async def get_async_db_legacy() -> AsyncGenerator[AsyncSession, None]:
    initialize_database()

    if AsyncSessionLocal is None:
        raise RuntimeError("Database not properly initialized")

    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_async_db_context_legacy():
    initialize_database()

    if AsyncSessionLocal is None:
        raise RuntimeError("Database not properly initialized")

    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_database():
    """Initialize database tables – call during application startup"""
    try:
        logger.info("Initializing database tables...")
        initialize_database()

        if async_engine is None:
            raise RuntimeError("Database engine not initialized")

        async with async_engine.begin() as conn:

            await conn.run_sync(Base.metadata.create_all)

        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {type(e).__name__}: {e}")
        raise


async def close_database():
    """Close database connections"""
    global async_engine
    if async_engine is not None:
        await async_engine.dispose()
        async_engine = None


async def check_database_health() -> bool:
    """Check if database connection is healthy"""
    try:
        initialize_database()

        if AsyncSessionLocal is None:
            return False

        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
            return True

    except Exception as e:
        logger.error(f"Database health check failed: {type(e).__name__}: {e}")
        return False

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

def initialize_database() -> None:
    """Initialize database engine and session factory"""
    global async_engine, AsyncSessionLocal

    if async_engine is not None:
        return  # already initialized

    if not settings.DATABASE_URL:
        logger.error("DATABASE_URL is required but not set")
        raise ValueError("DATABASE_URL is required but not set")

    database_url = settings.DATABASE_URL.strip()
    logger.debug(f"Original DATABASE_URL: {database_url!r}")

    # Force asyncpg driver
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif database_url.startswith("postgresql://") and "+asyncpg" not in database_url:
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    # Никаких правок sslmode и прочей херни – даем SQLAlchemy сделать свое дело
    logger.info("Initializing async database engine")

    try:
        engine_kwargs = {
            "echo": False,
            "pool_pre_ping": True,
            "pool_size": 20,
            "max_overflow": 30,
            "pool_timeout": 30,
            "pool_recycle": 3600,
        }

        if "sqlite" in database_url:
            engine_kwargs["poolclass"] = StaticPool

        engine = create_async_engine(database_url, **engine_kwargs)
        AsyncSessionLocal = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )

        globals()["async_engine"] = engine
        logger.info("Database engine initialized successfully")
    except Exception as e:
        logger.error(f"Failed to create database engine: {type(e).__name__}: {e}")
        raise


# Base class for all models
Base = declarative_base()


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


# Legacy compatibility functions (use the versions above)
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
            logger.error("Database engine not initialized")
            raise RuntimeError("Database engine not initialized")

        async with async_engine.begin() as conn:
            from app.db.models import (
                User,
                Expense,
                Transaction,
                Goal,
                Habit,
                Mood,
                DailyPlan,
                Subscription,
                PushToken,
                NotificationLog,
                UserAnswer,
                UserProfile,
                AIAnalysisSnapshot,
                BudgetAdvice,
                AIAdviceTemplate,
            )  # noqa

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
            logger.error("AsyncSessionLocal is None - database not initialized")
            return False

        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
            return True
    except Exception as e:
        logger.error(f"Database health check failed: {type(e).__name__}: {e}")
        return False

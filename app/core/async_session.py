"""
Async Database Session Management for MITA
Provides async SQLAlchemy session handling with proper connection management and monitoring
"""

import logging
from typing import AsyncGenerator
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import text

from app.core.config import settings
from app.core.database_monitoring import db_engine

logger = logging.getLogger(__name__)

# Global engine/session objects
async_engine = None
AsyncSessionLocal = None


def initialize_database():
    """Initialize async database engine and session factory"""
    global async_engine, AsyncSessionLocal

    # Already initialized
    if async_engine is not None:
        return

    if not settings.DATABASE_URL:
        logger.error("DATABASE_URL is required but not set")
        raise ValueError("DATABASE_URL is required but not set")

    logger.debug(f"Original DATABASE_URL: {settings.DATABASE_URL[:80]}")

    # FORCE asyncpg driver but DO NOT modify sslmode
    database_url = settings.DATABASE_URL

    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif "postgresql+psycopg2" in database_url:
        database_url = database_url.replace("postgresql+psycopg2", "postgresql+asyncpg")

    # IMPORTANT:
    # DO NOT TOUCH sslmode=require
    # asyncpg works with it natively when passed via URL

    logger.debug(f"Converted DATABASE_URL: {database_url[:80]}")

    # Create async engine (clean version)
    try:
        async_engine = create_async_engine(
            database_url,
            echo=False,
            pool_pre_ping=True,
            pool_size=20,
            max_overflow=30,
            pool_timeout=30,
            pool_recycle=3600,
            # ONLY sqlite uses StaticPool
            poolclass=None,
            connect_args={
                # REQUIRED for Supabase's pgBouncer
                "statement_cache_size": 0,
                # SSL REQUIRED by Supabase
                "ssl": "require",
                # Optional metadata
                "server_settings": {
                    "application_name": "mita_finance_app"
                },
                # Supabase timeout compatibility
                "command_timeout": 10
            },
            execution_options={
                "isolation_level": "READ_COMMITTED"
            }
        )

        logger.info("Database engine initialized successfully")

    except Exception as e:
        logger.error(f"Database engine creation failed: {type(e).__name__}: {str(e)}")
        raise

    # Create session factory
    AsyncSessionLocal = async_sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )


# Base ORM model
Base = declarative_base()


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for DB sessions"""
    initialize_database()

    if AsyncSessionLocal is None:
        raise RuntimeError("Database not initialized")

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
    initialize_database()

    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# Legacy (still kept for older routes)
async def get_async_db_legacy() -> AsyncGenerator[AsyncSession, None]:
    initialize_database()
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
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# Create all tables
async def init_database():
    try:
        logger.info("Initializing database tables...")
        initialize_database()

        async with async_engine.begin() as conn:
            from app.db.models import (
                User, Expense, Transaction, Goal, Habit, Mood,
                DailyPlan, Subscription, PushToken, NotificationLog,
                UserAnswer, UserProfile, AIAnalysisSnapshot,
                BudgetAdvice, AIAdviceTemplate
            )
            await conn.run_sync(Base.metadata.create_all)

        logger.info("Database tables created successfully")

    except Exception as e:
        logger.error(f"Database initialization failed: {type(e).__name__}: {str(e)}")
        raise


async def close_database():
    global async_engine
    if async_engine is not None:
        await async_engine.dispose()
        async_engine = None


async def check_database_health() -> bool:
    try:
        initialize_database()
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {type(e).__name__}: {str(e)}")
        return False

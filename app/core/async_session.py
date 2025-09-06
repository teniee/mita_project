"""
Async Database Session Management for MITA
Provides async SQLAlchemy session handling with proper connection management and monitoring
"""

import logging
from typing import AsyncGenerator
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import StaticPool
from sqlalchemy import text

from app.core.config import settings
from app.core.database_monitoring import db_engine

logger = logging.getLogger(__name__)

# Database engine and session - initialized lazily
async_engine = None
AsyncSessionLocal = None

def initialize_database():
    """Initialize database engine and session factory"""
    global async_engine, AsyncSessionLocal
    
    if async_engine is not None:
        return  # Already initialized
    
    if not settings.DATABASE_URL:
        import logging
        logger = logging.getLogger(__name__)
        logger.error("DATABASE_URL is required but not set")
        raise ValueError("DATABASE_URL is required but not set")
    
    import logging
    logger = logging.getLogger(__name__)
    logger.debug(f"Original DATABASE_URL format: {settings.DATABASE_URL[:50]}...")
    
    # FORCE asyncpg driver - direct URL conversion
    database_url = settings.DATABASE_URL
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif "postgresql+psycopg2" in database_url:
        database_url = database_url.replace("postgresql+psycopg2", "postgresql+asyncpg")
    
    # Fix SSL parameters for asyncpg
    if "sslmode=" in database_url:
        database_url = database_url.replace("sslmode=", "ssl=")
    
    logger.debug(f"Converted DATABASE_URL format: {database_url[:50]}...")
    
    
    # Create async engine with optimized settings for Render/production performance
    try:
        logger.debug("Creating database engine...")
        # Add URL parameter to ensure statement cache is disabled at connection level
        if "postgresql" in database_url and "statement_cache_size" not in database_url:
            separator = "&" if "?" in database_url else "?"
            database_url = f"{database_url}{separator}statement_cache_size=0"
            logger.debug(f"Added statement_cache_size=0 to URL: {database_url[:50]}...")
        
        async_engine = create_async_engine(
            database_url,
            echo=False,  # Always disable echo for performance
            pool_pre_ping=True,
            # OPTIMIZED connection pooling for database performance
            pool_size=20,           # Increased from 3 to handle concurrent users
            max_overflow=30,        # Increased from 7 to handle traffic spikes
            pool_timeout=30,        # Increased from 5 for stability
            pool_recycle=3600,      # 1 hour - standard recycle time
            # Use StaticPool for SQLite, QueuePool for PostgreSQL (default)
            poolclass=StaticPool if "sqlite" in database_url else None,
            connect_args={
                "server_settings": {
                    "application_name": "mita_finance_app"
                },
                "command_timeout": 10,  # Increase timeout for Supabase compatibility
                "statement_cache_size": 0,  # Disable prepared statements for pgbouncer compatibility
            } if "postgresql" in database_url else {},
            # Performance optimizations
            pool_reset_on_return='commit',  # Only reset on commit, not rollback
            execution_options={
                "isolation_level": "READ_COMMITTED"  # Faster isolation level
            }
        )
        logger.info("Database engine created successfully")
    except Exception as e:
        logger.error(f"Failed to create database engine: {type(e).__name__}: {str(e)}")
        raise
    
    # Create async session factory with optimized settings
    AsyncSessionLocal = async_sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,     # Don't expire objects after commit for better performance
        autoflush=False,            # Manual flushing for better control
        autocommit=False,           # Manual transactions
    )

# Base class for all models
Base = declarative_base()


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Async database dependency for FastAPI
    Provides proper async session management with automatic cleanup and monitoring
    """
    # Initialize database if not already done
    initialize_database()
    
    if AsyncSessionLocal is None:
        raise RuntimeError("Database not properly initialized")
    
    # Create a new session
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
    """
    Context manager for async database operations
    Use when you need manual transaction control
    """
    # Initialize database if not already done
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


# Legacy compatibility functions (use the monitored versions above)
async def get_async_db_legacy() -> AsyncGenerator[AsyncSession, None]:
    """
    Legacy async database dependency - use get_async_db() instead
    """
    # Initialize database if not already done
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
    """
    Legacy context manager - use get_async_db_context() instead
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


async def init_database():
    """
    Initialize database tables
    Call this during application startup
    """
    try:
        logger.info("Starting database table initialization...")
        # Initialize the database connection first
        initialize_database()
        
        if async_engine is None:
            logger.error("Database engine not initialized")
            raise RuntimeError("Database engine not initialized")
        
        logger.debug("Creating database tables...")
        async with async_engine.begin() as conn:
            # Import all models to ensure they are registered
            from app.db.models import (
                User, Expense, Transaction, Goal, Habit, Mood, 
                DailyPlan, Subscription, PushToken, NotificationLog,
                UserAnswer, UserProfile, AIAnalysisSnapshot, BudgetAdvice, AIAdviceTemplate
            )  # noqa
            logger.debug("Models imported, creating tables...")
            # Create all tables
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {type(e).__name__}: {str(e)}")
        raise


async def close_database():
    """
    Close database connections
    Call this during application shutdown
    """
    global async_engine
    if async_engine is not None:
        await async_engine.dispose()
        async_engine = None


# Health check function
async def check_database_health() -> bool:
    """
    Check if database connection is healthy
    Returns True if connection is working, False otherwise
    """
    try:
        # Initialize database if not already done
        initialize_database()
        
        if AsyncSessionLocal is None:
            logger.error("AsyncSessionLocal is None - database not initialized")
            return False
            
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
            return True
    except Exception as e:
        logger.error(f"Database health check failed: {type(e).__name__}: {str(e)}")
        return False
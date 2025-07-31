"""
Async Database Session Management for MITA
Provides async SQLAlchemy session handling with proper connection management and monitoring
"""

from typing import AsyncGenerator
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.database_monitoring import db_engine

# Database engine and session - initialized lazily
async_engine = None
AsyncSessionLocal = None

def initialize_database():
    """Initialize database engine and session factory"""
    global async_engine, AsyncSessionLocal
    
    if async_engine is not None:
        return  # Already initialized
    
    if not settings.DATABASE_URL:
        raise ValueError("DATABASE_URL is required but not set")
    
    # Use the ASYNC_DATABASE_URL property which ensures asyncpg driver
    database_url = settings.ASYNC_DATABASE_URL
    
    # Verify code changes are deployed
    if not hasattr(settings, 'ASYNC_DATABASE_URL'):
        raise RuntimeError("CRITICAL: ASYNC_DATABASE_URL property missing - code changes not deployed!")
    
    print("[DEBUG] Using ASYNC_DATABASE_URL property for asyncpg driver")
    
    # Create async engine with optimized settings
    async_engine = create_async_engine(
        database_url,
        echo=getattr(settings, 'DEBUG', False),
        pool_pre_ping=True,
        pool_size=20,
        max_overflow=30,
        pool_timeout=30,
        pool_recycle=3600,  # Recycle connections every hour
        # Use StaticPool for SQLite, QueuePool for PostgreSQL (default)
        poolclass=StaticPool if "sqlite" in database_url else None,
        connect_args={
            "server_settings": {
                "application_name": "mita_finance_app",
                "jit": "off",  # Disable JIT for faster connections
            }
        } if "postgresql" in database_url else {}
    )
    
    # Create async session factory
    AsyncSessionLocal = async_sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False
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
    # Initialize the database connection first
    initialize_database()
    
    if async_engine is None:
        raise RuntimeError("Database engine not initialized")
    
    async with async_engine.begin() as conn:
        # Import all models to ensure they are registered
        from app.db.models import User, Expense, Transaction  # noqa
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)


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
            return False
            
        async with AsyncSessionLocal() as session:
            await session.execute("SELECT 1")
            return True
    except Exception:
        return False
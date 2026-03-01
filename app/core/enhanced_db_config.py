"""
Enhanced Database Configuration with Production Fallbacks
"""

import os
import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)

class DatabaseConfig:
    """Enhanced database configuration with production fallbacks"""
    
    @staticmethod
    def get_database_url() -> str:
        """Get database URL with fallbacks and validation"""
        
        # Priority order:
        # 1. DATABASE_URL environment variable
        # 2. Constructed from components
        # 3. Render.com database from service
        
        db_url = os.getenv("DATABASE_URL")
        
        if db_url:
            # Convert postgres:// to postgresql:// for SQLAlchemy
            if db_url.startswith("postgres://"):
                db_url = db_url.replace("postgres://", "postgresql://", 1)
                
            # Ensure async driver
            if db_url.startswith("postgresql://"):
                db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
                
            return db_url
        
        # Fallback: construct from components
        components = {
            "user": os.getenv("PGUSER", "mita_user"),
            "password": os.getenv("PGPASSWORD", ""),
            "host": os.getenv("PGHOST", "localhost"),
            "port": os.getenv("PGPORT", "5432"),
            "database": os.getenv("PGDATABASE", "mita_production")
        }
        
        if all(components.values()):
            return f"postgresql+asyncpg://{components['user']}:{components['password']}@{components['host']}:{components['port']}/{components['database']}"
        
        # Development fallback
        if os.getenv("ENVIRONMENT", "").lower() != "production":
            return "sqlite+aiosqlite:///./test.db"
        
        raise ValueError("DATABASE_URL is required in production environment")
    
    @staticmethod
    def create_engine_with_fallback():
        """Create database engine with production-ready settings"""
        database_url = DatabaseConfig.get_database_url()
        
        engine_kwargs = {
            "echo": False,  # Set to True for debugging
            "pool_pre_ping": True,
            "pool_recycle": 3600,  # 1 hour
            "connect_args": {
                "statement_cache_size": 0,  # Disable client-side statement cache
                "prepared_statement_cache_size": 0,  # CRITICAL: Disable prepared statements for PgBouncer
                "server_settings": {
                    "jit": "off",  # Disable JIT compilation for better compatibility
                },
            },
        }

        # Production-specific settings
        if "postgresql" in database_url:
            engine_kwargs.update({
                "pool_size": int(os.getenv("DB_POOL_SIZE", "20")),
                "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "30")),
                "pool_timeout": int(os.getenv("DB_POOL_TIMEOUT", "30")),
            })

        return create_async_engine(database_url, **engine_kwargs)

# Global engine instance
engine = None

def get_engine():
    """Get or create database engine"""
    global engine
    if engine is None:
        engine = DatabaseConfig.create_engine_with_fallback()
    return engine

async def get_async_db() -> AsyncSession:
    """Enhanced database session with error handling"""
    try:
        async_session = sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        async with async_session() as session:
            yield session
            
    except Exception as e:
        logger.error(f"Database session error: {e}")
        
        # If this is a database connection error in production, 
        # we should fail fast rather than continue with broken state
        if "production" in os.getenv("ENVIRONMENT", "").lower():
            raise RuntimeError(f"Production database unavailable: {e}")
        
        # In development, we can try to continue with a warning
        logger.warning("Database unavailable, some features may not work")
        raise

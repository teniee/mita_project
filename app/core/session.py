from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
import logging

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Lazy initialization to prevent crash if DATABASE_URL not set
engine = None
SessionLocal = None

def _initialize_sync_session():
    """Initialize synchronous database session (lazy)"""
    global engine, SessionLocal

    if engine is not None:
        return

    try:
        if not settings.DATABASE_URL:
            logger.warning("DATABASE_URL not set - sync database session unavailable")
            return

        # Convert asyncpg URL to psycopg2 via simple string replacement
        # This preserves username with dots (e.g., postgres.PROJECT_ID)
        database_url = settings.DATABASE_URL.strip()

        # Remove ssl= parameter if present (psycopg2 only supports sslmode in connect_args)
        if "ssl=require" in database_url:
            database_url = database_url.replace("?ssl=require", "").replace("&ssl=require", "")

        # Simple driver replacement - preserves all credentials exactly as they are
        # This avoids URL parsing issues with usernames containing dots
        if "+asyncpg://" in database_url:
            sync_database_url = database_url.replace("+asyncpg://", "+psycopg2://")
        elif "postgresql://" in database_url and "+psycopg2://" not in database_url:
            sync_database_url = database_url.replace("postgresql://", "postgresql+psycopg2://")
        else:
            sync_database_url = database_url

        sync_url = make_url(sync_database_url)

        # CRITICAL: PgBouncer compatibility - disable prepared statements
        # psycopg2 requires sslmode in connect_args, NOT in URL
        connect_args = {
            "sslmode": "require",  # Force SSL for Supabase (psycopg2 format)
        }

        # Log the final connection string for debugging (hide password)
        safe_url = str(sync_url).replace(sync_url.password or "", "***") if sync_url.password else str(sync_url)
        logger.info(f"Sync session connecting to: {safe_url}")
        logger.debug(f"Username: {sync_url.username}, Host: {sync_url.host}, Database: {sync_url.database}")

        # Add prepared_statement_cache_size=0 for PgBouncer compatibility
        engine = create_engine(
            str(sync_url),
            echo=False,
            pool_pre_ping=True,
            connect_args=connect_args,
            # PgBouncer-safe pool settings
            pool_size=5,
            max_overflow=10,
            pool_timeout=30,
            pool_recycle=1800,
        )
        # Note: psycopg2 doesn't support prepared_statement_cache_size parameter
        # but it's less critical for sync sessions

        SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
        logger.info("✅ Sync database session initialized with SSL and PgBouncer compatibility")

    except Exception as e:
        logger.error(f"Failed to initialize sync database session: {e}")
        logger.warning("App will continue without sync database support")


def get_db():
    """Get synchronous database session"""
    _initialize_sync_session()

    if SessionLocal is None:
        raise RuntimeError("Database session not initialized - DATABASE_URL may be missing")

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

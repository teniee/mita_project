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

        # Convert asyncpg URL to psycopg2 and preserve SSL + PgBouncer compatibility
        database_url = settings.DATABASE_URL.strip()

        # Ensure SSL requirement (required by Supabase)
        if "ssl=" not in database_url and "sslmode=" not in database_url:
            sep = "&" if "?" in database_url else "?"
            database_url += f"{sep}ssl=require"

        sync_url = make_url(database_url)
        if sync_url.drivername.endswith("+asyncpg"):
            sync_url = sync_url.set(drivername="postgresql+psycopg2")

        # CRITICAL: PgBouncer compatibility - disable prepared statements
        connect_args = {
            "sslmode": "require",  # Force SSL for Supabase
        }

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

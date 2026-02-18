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

        # Parse asyncpg URL and extract credentials
        database_url = settings.DATABASE_URL.strip()

        # Remove ssl= parameter if present (psycopg2 only supports sslmode in connect_args)
        if "ssl=require" in database_url:
            database_url = database_url.replace("?ssl=require", "").replace("&ssl=require", "")

        # Parse the URL to extract components
        parsed = make_url(database_url)

        # CRITICAL FIX: Pass username and password via connect_args to bypass psycopg2 URL parsing
        # psycopg2 truncates usernames with dots when parsed from URL
        # Solution: Build URL without credentials, pass them separately

        # Build connection URL WITHOUT username/password
        host = parsed.host or "localhost"
        port = parsed.port or 5432
        database = parsed.database or ""
        sync_database_url = f"postgresql+psycopg2://{host}:{port}/{database}"

        # Pass credentials via connect_args (bypasses psycopg2 URL parsing)
        connect_args = {
            "user": parsed.username,      # Username with dot will be preserved
            "password": parsed.password,  # Password passed separately
            "sslmode": "require",         # Force SSL for Supabase
        }

        sync_url = make_url(sync_database_url)

        # Log the connection details for debugging
        logger.info(f"Sync session connecting to: {host}:{port}/{database}")
        logger.info(f"Username (via connect_args): {parsed.username}")

        # Create engine with credentials in connect_args
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

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

        sync_url = make_url(settings.DATABASE_URL)
        if sync_url.drivername.endswith("+asyncpg"):
            sync_url = sync_url.set(drivername="postgresql+psycopg2")

        engine = create_engine(str(sync_url), echo=False, pool_pre_ping=True)
        SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
        logger.info("✅ Sync database session initialized")

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

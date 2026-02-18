from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
import logging

from app.core.config import settings

# Import Base so that Alembic can discover models; it's unused directly here.
from app.db.base import Base  # noqa: F401

logger = logging.getLogger(__name__)

# Lazy initialization to prevent crash if DATABASE_URL not set
engine = None
async_session = None

def _initialize_async_engine():
    """Initialize async database engine (lazy)"""
    global engine, async_session

    if engine is not None:
        return

    try:
        # Use the ASYNC_DATABASE_URL property which ensures asyncpg driver
        DATABASE_URL = settings.ASYNC_DATABASE_URL

        if not DATABASE_URL:
            logger.warning("DATABASE_URL not set - async database engine unavailable")
            return

        # Verify code changes are deployed
        if not hasattr(settings, 'ASYNC_DATABASE_URL'):
            raise RuntimeError("CRITICAL: Code changes not deployed - ASYNC_DATABASE_URL missing!")

        # asyncpg doesn't support sslmode parameter, remove it if present
        # Supabase connections already use SSL by default with asyncpg
        if "?sslmode=" in DATABASE_URL:
            DATABASE_URL = DATABASE_URL.split("?sslmode=")[0]
        elif "&sslmode=" in DATABASE_URL:
            import re
            DATABASE_URL = re.sub(r'&sslmode=[^&]*', '', DATABASE_URL)

        url = make_url(DATABASE_URL)

        # Additional safety check - if somehow it's still not asyncpg, force it
        if url.drivername in ["postgresql", "postgresql+psycopg2", "postgres"]:
            url = url.set(drivername="postgresql+asyncpg")

        engine = create_async_engine(
            url.render_as_string(hide_password=False),
            future=True,
            echo=False,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            pool_timeout=30,
            pool_recycle=1800,
            connect_args={
                "statement_cache_size": 0,  # Disable client-side statement cache
                "prepared_statement_cache_size": 0,  # CRITICAL: Disable prepared statements for PgBouncer
                "server_settings": {
                    "jit": "off",  # Disable JIT compilation for better compatibility
                },
            },
        )

        async_session = async_sessionmaker(
            bind=engine,
            expire_on_commit=False,
        )

        logger.info("✅ Async database engine initialized")

    except Exception as e:
        logger.error(f"Failed to initialize async database engine: {e}")
        logger.warning("App will continue without async database support")


async def get_db():
    """Get async database session"""
    _initialize_async_engine()

    if async_session is None:
        raise RuntimeError("Database engine not initialized - DATABASE_URL may be missing")

    async with async_session() as session:
        yield session

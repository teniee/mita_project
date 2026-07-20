import logging

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Lazy initialization to prevent crash if DATABASE_URL not set
engine = None
SessionLocal = None


def _resolve_sslmode(query):
    """psycopg2 sslmode from the URL's query parameters.

    Honors an explicit sslmode= (or asyncpg-style ssl=) parameter; only
    when the URL says nothing do we default to "require" (hosted Postgres
    like Supabase). Forcing "require" unconditionally broke every
    deployment whose Postgres has SSL off (CI service containers,
    docker-compose, private networking).
    """
    value = str(query.get("sslmode") or query.get("ssl") or "").lower()
    if value in ("true", "require"):
        return "require"
    if value in ("false", "disable"):
        return "disable"
    if value in ("allow", "prefer", "verify-ca", "verify-full"):
        return value
    return "require"


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
            "user": parsed.username,  # Username with dot will be preserved
            "password": parsed.password,  # Password passed separately
            "sslmode": _resolve_sslmode(parsed.query),
            # The codebase's naive-datetime convention means UTC. Prod PG
            # already runs Etc/UTC; pin the session too so a dev/CI server
            # with a local timezone (e.g. Europe/Sofia) can't shift
            # naive-bound windows by the UTC offset.
            "options": "-c timezone=UTC",
        }

        sync_url = make_url(sync_database_url)

        # Log connection target only — never log credentials (C-04 security fix)
        logger.info(f"Sync session connecting to: {host}:{port}/{database}")

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
        logger.info(
            "✅ Sync database session initialized with SSL and PgBouncer compatibility"
        )

    except Exception as e:
        logger.error(f"Failed to initialize sync database session: {e}")
        logger.warning("App will continue without sync database support")


def get_db():
    """Get synchronous database session"""
    _initialize_sync_session()

    if SessionLocal is None:
        raise RuntimeError(
            "Database session not initialized - DATABASE_URL may be missing"
        )

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_sync_session():
    """Create a sync Session for code outside FastAPI dependency injection.

    `SessionLocal` is initialized lazily by get_db(), so services that read
    the module attribute directly see None until some get_db() route has run
    in the same process — in production that made the first
    `SessionLocal()` caller crash with "'NoneType' object is not callable".
    Callers own the session and must close() it.
    """
    _initialize_sync_session()

    if SessionLocal is None:
        raise RuntimeError(
            "Database session not initialized - DATABASE_URL may be missing"
        )

    return SessionLocal()

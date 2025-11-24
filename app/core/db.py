from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.core.config import settings

# Import Base so that Alembic can discover models; it's unused directly here.
from app.db.base import Base  # noqa: F401

# Use the ASYNC_DATABASE_URL property which ensures asyncpg driver
DATABASE_URL = settings.ASYNC_DATABASE_URL

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


async def get_db():
    async with async_session() as session:
        yield session

from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.core.config import settings

# Import Base so that Alembic can discover models; it's unused directly here.
from app.db.base import Base  # noqa: F401

# CRITICAL TEST: This should crash if changes aren't deployed
print("=" * 80)
print("🚨 CRITICAL DEPLOYMENT TEST - IF YOU SEE THIS, CHANGES ARE DEPLOYED 🚨")
print("=" * 80)

# Use the ASYNC_DATABASE_URL property which ensures asyncpg driver
DATABASE_URL = settings.ASYNC_DATABASE_URL

print(f"[URGENT DEBUG db.py] Using ASYNC_DATABASE_URL: {DATABASE_URL}")
print(f"[URGENT DEBUG db.py] Original DATABASE_URL: {settings.DATABASE_URL}")

# Force crash if this code isn't running correctly
if not hasattr(settings, 'ASYNC_DATABASE_URL'):
    raise RuntimeError("🚨 CRITICAL: Code changes not deployed - ASYNC_DATABASE_URL missing!")
    
if DATABASE_URL == settings.DATABASE_URL and DATABASE_URL.startswith(('postgresql://', 'postgres://')):
    raise RuntimeError(f"🚨 CRITICAL: URL conversion failed! Got: {DATABASE_URL}")

# Parse the URL to verify it has the correct driver
url = make_url(DATABASE_URL)
print(f"[DEBUG db.py] Parsed URL drivername: {url.drivername}")

# Additional safety check - if somehow it's still not asyncpg, force it
if url.drivername in ["postgresql", "postgresql+psycopg2", "postgres"]:
    url = url.set(drivername="postgresql+asyncpg")
    print(f"[DEBUG db.py] FORCED conversion to: {url.drivername}")
else:
    print(f"[DEBUG db.py] URL drivername is already correct: {url.drivername}")

engine = create_async_engine(
    url.render_as_string(hide_password=False),
    future=True,
    echo=False,
)

async_session = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
)


async def get_db():
    async with async_session() as session:
        yield session

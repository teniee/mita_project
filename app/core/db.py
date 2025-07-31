from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.core.config import settings

# Import Base so that Alembic can discover models; it's unused directly here.
from app.db.base import Base  # noqa: F401

DATABASE_URL = settings.DATABASE_URL

# Ensure that an async driver is used even if the provided DATABASE_URL is
# synchronous (e.g. ``postgresql://``). ``alembic upgrade`` would otherwise
# fail with ``InvalidRequestError: The asyncio extension requires an async
# driver to be used``.
url = make_url(DATABASE_URL)
if url.drivername in ["postgresql", "postgresql+psycopg2"]:
    url = url.set(drivername="postgresql+asyncpg")

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

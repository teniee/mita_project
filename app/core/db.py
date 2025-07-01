from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

DATABASE_URL = settings.DATABASE_URL

try:
    engine = create_async_engine(DATABASE_URL, future=True, echo=False)
except ModuleNotFoundError:  # pragma: no cover - fallback for tests
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", future=True, echo=False
    )
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()  # added for legacy code

async def get_db():
    async with async_session() as session:
        yield session

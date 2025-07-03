from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings

settings = get_settings()

sync_url = make_url(settings.DATABASE_URL)
if sync_url.drivername.endswith("+asyncpg"):
    sync_url = sync_url.set(drivername="postgresql+psycopg2")

engine = create_engine(str(sync_url), echo=False, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

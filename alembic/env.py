import os
import sys
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine.url import make_url

from alembic import context


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.models import Base  # <-- Импорт только Base и моделей

config = context.config
fileConfig(config.config_file_name)

target_metadata = Base.metadata


url = config.get_main_option("sqlalchemy.url")
sync_url = make_url(url)
if sync_url.drivername.endswith("+asyncpg"):
    sync_url = sync_url.set(drivername="postgresql+psycopg2")

def run_migrations_offline():
    context.configure(
        url=str(sync_url),
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

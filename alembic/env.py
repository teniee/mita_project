import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine.url import make_url

from alembic import context

# Include your app for model imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import Base where all models are attached
from app.db.models import Base

# Load Alembic config
config = context.config

# Setup loggers
fileConfig(config.config_file_name)

# Set your target metadata
target_metadata = Base.metadata

# Get the database URL and replace async driver with sync if needed
url = config.get_main_option("sqlalchemy.url")
sync_url = make_url(url)
if sync_url.drivername.endswith("+asyncpg"):
    sync_url = sync_url.set(drivername="postgresql+psycopg2")


def run_migrations_offline():
    """Run migrations in 'offline' mode."""
    context.configure(
        url=str(sync_url),
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

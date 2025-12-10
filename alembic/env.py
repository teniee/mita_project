import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine.url import make_url

from alembic import context

# Include your app for model imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import app.db.models  # noqa: F401

# Import Base where all models are attached
# Import Base and all models so Alembic can detect schema changes
from app.db.models.base import Base

# Load Alembic config
config = context.config

# Setup loggers
fileConfig(config.config_file_name)

# Set your target metadata
target_metadata = Base.metadata

# Get the database URL - try environment variable first, then config
url = os.environ.get("DATABASE_URL") or config.get_main_option("sqlalchemy.url")
if not url:
    raise ValueError(
        "No database URL found. Set DATABASE_URL environment variable or "
        "configure sqlalchemy.url in alembic.ini"
    )

# Debug: Log URL structure (without password)
print(f"[Alembic] Database URL detected: {url.split('@')[0].split(':')[0]}://***@{url.split('@')[1] if '@' in url else 'no-host'}")

try:
    sync_url = make_url(url)

    # Convert asyncpg to psycopg2 driver
    if sync_url.drivername.endswith("+asyncpg"):
        sync_url = sync_url.set(drivername="postgresql+psycopg2")
        print(f"[Alembic] Converted driver: asyncpg -> psycopg2")

    # Remove Supabase-specific query parameters that psycopg2 doesn't support
    # psycopg2 uses sslmode instead of ssl, and doesn't support prepared_statement_cache_size
    if sync_url.query:
        filtered_query = {}
        for k, v in sync_url.query.items():
            if k == 'ssl' and v == 'require':
                filtered_query['sslmode'] = 'require'  # Convert to psycopg2 format
            elif k not in ['prepared_statement_cache_size', 'ssl', 'statement_cache_size', 'server_settings']:
                filtered_query[k] = v
        sync_url = sync_url.set(query=filtered_query)
        print(f"[Alembic] Filtered query params: {list(filtered_query.keys())}")

    # Password is already properly handled by SQLAlchemy's make_url()
    # No need to re-encode - it will cause authentication failures
    print(f"[Alembic] Final connection: {sync_url.host}:{sync_url.port} database={sync_url.database}")

except Exception as e:
    print(f"[Alembic ERROR] Failed to parse DATABASE_URL: {e}")
    raise


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
    # Create engine directly with our URL (already validated above)
    from sqlalchemy import create_engine
    connectable = create_engine(
        str(sync_url),
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

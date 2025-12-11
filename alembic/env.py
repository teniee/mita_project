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

# Get the database URL - try migration-specific URL first, then DATABASE_URL, then config
# MIGRATION_DATABASE_URL can use direct connection (port 5432) for Supabase
# while DATABASE_URL should use session pooler (port 6543 with ?pgbouncer=true) for the app
url = (
    os.environ.get("MIGRATION_DATABASE_URL") or
    os.environ.get("DATABASE_URL") or
    config.get_main_option("sqlalchemy.url")
)
if not url:
    raise ValueError(
        "No database URL found. Set DATABASE_URL environment variable or "
        "configure sqlalchemy.url in alembic.ini"
    )

# Auto-configure Supabase pooler for migrations
# Session pooler (port 5432 on pooler host) supports long-running migrations
# Transaction pooler (port 6543) does NOT support migrations
if "supabase.com" in url and ":6543/" in url:
    print("[Alembic] Supabase Transaction pooler detected (port 6543)")
    print("[Alembic] Switching to Session pooler (port 5432) for migrations")
    url = url.replace(":6543/", ":5432/")
    print("[Alembic] Session pooler enabled - supports long-running migrations")
    print("[Alembic] Set MIGRATION_DATABASE_URL env var to use direct connection instead")

# Debug: Log URL structure (without password)
print(f"[Alembic] Database URL detected: {url.split('@')[0].split(':')[0]}://***@{url.split('@')[1] if '@' in url else 'no-host'}")

try:
    sync_url = make_url(url)

    # Convert asyncpg to psycopg2 driver
    if sync_url.drivername.endswith("+asyncpg"):
        sync_url = sync_url.set(drivername="postgresql+psycopg2")
        print(f"[Alembic] Converted driver: asyncpg -> psycopg2")

    # Remove Supabase-specific query parameters that psycopg2 doesn't support
    # psycopg2 uses sslmode instead of ssl
    if sync_url.query:
        filtered_query = {}
        # List of params to exclude (not supported by psycopg2)
        excluded_params = ['prepared_statement_cache_size', 'ssl', 'statement_cache_size',
                          'server_settings', 'pgbouncer']

        for k, v in sync_url.query.items():
            if k == 'ssl' and v == 'require':
                # Convert Supabase 'ssl=require' to psycopg2 'sslmode=require'
                filtered_query['sslmode'] = 'require'
            elif k not in excluded_params:
                # Keep all other valid params
                filtered_query[k] = v

        sync_url = sync_url.set(query=filtered_query)
        print(f"[Alembic] Query params after filtering: {list(filtered_query.keys())}")

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

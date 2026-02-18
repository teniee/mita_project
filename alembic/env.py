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
# Note: Using Transaction pooler (port 6543) for migrations
# For long-running migrations, set MIGRATION_DATABASE_URL with direct connection
if "supabase.com" in url and ":6543/" in url:
    print("[Alembic] Supabase Transaction pooler detected (port 6543)")
    print("[Alembic] Using Transaction pooler for migrations")
    print("[Alembic] Note: For long-running migrations, set MIGRATION_DATABASE_URL env var")

# Debug: Log URL structure (without password)
print(f"[Alembic] Database URL detected: {url.split('@')[0].split(':')[0]}://***@{url.split('@')[1] if '@' in url else 'no-host'}")

# Simple string replacement for asyncpg -> psycopg2 WITHOUT using make_url() to avoid password encoding issues
final_url = url
if "+asyncpg://" in url:
    final_url = url.replace("+asyncpg://", "+psycopg2://", 1)
    print(f"[Alembic] Converted driver: asyncpg -> psycopg2")
elif "postgresql://" in url and "+psycopg2://" not in url:
    final_url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    print(f"[Alembic] Added psycopg2 driver")

# Remove problematic query params for Supabase pooler
if "?" in final_url:
    base_url, query_string = final_url.split("?", 1)
    # Remove pgbouncer parameter as it's not needed for psycopg2
    params = [p for p in query_string.split("&") if not p.startswith("pgbouncer=")]
    if params:
        final_url = f"{base_url}?{'&'.join(params)}"
    else:
        final_url = base_url
    print(f"[Alembic] Cleaned query parameters")

# Extract host and port for logging WITHOUT using make_url()
try:
    if "@" in final_url:
        host_part = final_url.split("@")[1].split("/")[0]
        if ":" in host_part:
            host, port = host_part.rsplit(":", 1)
        else:
            host, port = host_part, "5432"
        db_name = final_url.split("/")[-1].split("?")[0] if "/" in final_url else "unknown"
        print(f"[Alembic] Final connection: {host}:{port} database={db_name}")
except Exception:
    print(f"[Alembic] Using connection string (parsing failed for logging)")

# Store as string, not make_url object - we'll create_engine directly with the string
sync_url = final_url


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

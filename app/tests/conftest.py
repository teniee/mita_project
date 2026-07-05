import os
import sys
import types

# Set DATABASE_URL for test environment BEFORE any imports
# This prevents "Could not parse SQLAlchemy URL from string ''" errors
os.environ.setdefault(
    "DATABASE_URL", "postgresql://test:test@localhost:5432/test_mita?sslmode=disable"
)
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_testing_only")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("TESTING", "true")
os.environ.setdefault("FIREBASE_JSON", "{}")

# SMTP Configuration for tests (prevent validation errors)
os.environ.setdefault("SMTP_HOST", "smtp.gmail.com")
os.environ.setdefault("SMTP_PORT", "587")
os.environ.setdefault("SMTP_USERNAME", "test@example.com")
os.environ.setdefault("SMTP_PASSWORD", "test_password")

# JWT Configuration
os.environ.setdefault("JWT_SECRET", "test_jwt_secret_key_min_32_chars_long_for_testing")

# Redis Configuration (optional for tests)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/1")

# External APIs (optional for tests)
os.environ.setdefault("OPENAI_API_KEY", "sk-test-key")
os.environ.setdefault(
    "GOOGLE_APPLICATION_CREDENTIALS", "/tmp/test-credentials.json"
)  # nosec B108 - fake path for test env

dummy = types.ModuleType("firebase_admin")
dummy._apps = []
dummy.credentials = types.SimpleNamespace(
    ApplicationDefault=lambda: None,
    Certificate=lambda *a, **k: None,
)
dummy.initialize_app = lambda cred=None: None

dummy.firestore = types.SimpleNamespace(
    client=lambda: types.SimpleNamespace(collection=lambda *a, **k: None)
)
dummy.messaging = types.SimpleNamespace(
    Message=lambda **kw: types.SimpleNamespace(**kw),
    Notification=lambda **kw: types.SimpleNamespace(**kw),
    send=lambda msg: "ok",
)

sys.modules.setdefault("firebase_admin", dummy)
sys.modules.setdefault("firebase_admin.credentials", dummy.credentials)
sys.modules.setdefault("firebase_admin.firestore", dummy.firestore)


# ---------------------------------------------------------------------------
# Async engine lifecycle between tests
#
# pytest-asyncio gives every test its own event loop, and each TestClient
# instance runs requests on its own portal loop. asyncpg connections are
# bound to the loop that created them, so a pool initialized in one test
# breaks DB access in the next ("attached to a different loop"). Dropping
# the engine reference after each test forces a fresh pool per loop.
# ---------------------------------------------------------------------------
import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_async_engine_between_tests():
    yield
    from app.core import async_session

    engine = async_session.async_engine
    async_session.async_engine = None
    async_session.AsyncSessionLocal = None
    if engine is not None:
        try:
            # Drop pool references without touching loop-bound connections;
            # asyncpg closes the underlying sockets on garbage collection.
            engine.sync_engine.dispose(close=False)
        except Exception:
            pass

    # dispose(close=False) can leave asyncpg sockets alive as
    # "idle in transaction" until GC runs (the loop that owns them is already
    # closed, so we cannot await their close here). Left unchecked they
    # accumulate over a long suite and eventually exhaust the connection pool,
    # making a late test's registration/DB write fail with a 500. Periodically
    # sweep them at the database level to keep the run stable.
    global _ENGINE_RESET_COUNTER
    _ENGINE_RESET_COUNTER += 1
    if _ENGINE_RESET_COUNTER % 40 == 0:
        _sweep_idle_connections()


_ENGINE_RESET_COUNTER = 0


def _sweep_idle_connections():
    """Terminate leaked 'idle in transaction' backends on the test database."""
    import re as _re

    url = os.environ.get("DATABASE_URL", "")
    if "postgres" not in url:
        return
    try:
        import psycopg2  # noqa: E402
    except Exception:
        return
    # Normalize SQLAlchemy/async URL to a psycopg2-compatible DSN.
    dsn = _re.sub(r"\+\w+", "", url).replace("sslmode=disable", "").rstrip("?&")
    try:
        conn = psycopg2.connect(dsn)
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = current_database() "
                "AND state = 'idle in transaction' "
                "AND pid <> pg_backend_pid()"
            )
        conn.close()
    except Exception:
        pass

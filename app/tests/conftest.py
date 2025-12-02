import os
import sys
import types

# Set DATABASE_URL for test environment BEFORE any imports
# This prevents "Could not parse SQLAlchemy URL from string ''" errors
os.environ.setdefault('DATABASE_URL', 'postgresql://test:test@localhost:5432/test_mita')
os.environ.setdefault('SECRET_KEY', 'test_secret_key_for_testing_only')
os.environ.setdefault('ENVIRONMENT', 'test')
os.environ.setdefault("FIREBASE_JSON", "{}")

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

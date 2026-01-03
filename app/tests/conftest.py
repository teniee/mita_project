import os
import sys
import types

# Set DATABASE_URL for test environment BEFORE any imports
# This prevents "Could not parse SQLAlchemy URL from string ''" errors
os.environ.setdefault('DATABASE_URL', 'postgresql://test:test@localhost:5432/test_mita?sslmode=disable')
os.environ.setdefault('SECRET_KEY', 'test_secret_key_for_testing_only')
os.environ.setdefault('ENVIRONMENT', 'test')
os.environ.setdefault("FIREBASE_JSON", "{}")

# SMTP Configuration for tests (prevent validation errors)
os.environ.setdefault('SMTP_HOST', 'smtp.gmail.com')
os.environ.setdefault('SMTP_PORT', '587')
os.environ.setdefault('SMTP_USERNAME', 'test@example.com')
os.environ.setdefault('SMTP_PASSWORD', 'test_password')

# JWT Configuration
os.environ.setdefault('JWT_SECRET', 'test_jwt_secret_key_min_32_chars_long_for_testing')

# Redis Configuration (optional for tests)
os.environ.setdefault('REDIS_URL', 'redis://localhost:6379/1')

# External APIs (optional for tests)
os.environ.setdefault('OPENAI_API_KEY', 'sk-test-key')
os.environ.setdefault('GOOGLE_APPLICATION_CREDENTIALS', '/tmp/test-credentials.json')

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

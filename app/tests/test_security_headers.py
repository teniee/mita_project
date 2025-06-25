import os
import sys
import types

from fastapi.testclient import TestClient

os.environ.setdefault("FIREBASE_JSON", "{}")

dummy = types.ModuleType("firebase_admin")
dummy._apps = []
dummy.credentials = types.SimpleNamespace(ApplicationDefault=lambda: None)
dummy.initialize_app = lambda cred=None: None


class DummyCollection:
    def document(self, *a, **k):
        return types.SimpleNamespace(
            set=lambda *a, **k: None,
            get=lambda: types.SimpleNamespace(
                to_dict=lambda: {},
                exists=False,
            ),
        )

    def where(self, *args, **kwargs):
        return []


dummy.firestore = types.SimpleNamespace(
    client=lambda: types.SimpleNamespace(
        collection=lambda *a, **k: DummyCollection(),
    ),
)
sys.modules["firebase_admin"] = dummy
sys.modules["firebase_admin.credentials"] = dummy.credentials
sys.modules["firebase_admin.firestore"] = dummy.firestore

from app.main import app  # noqa: E402

client = TestClient(app)


def test_security_headers_present():
    r = client.get("/docs")
    assert r.headers.get("Strict-Transport-Security")
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("X-Frame-Options") == "DENY"
    assert "default-src" in r.headers.get("Content-Security-Policy", "")
    assert r.headers.get("Permissions-Policy") == "geolocation=(), microphone=()"
    assert r.headers.get("Referrer-Policy") == "same-origin"
    assert r.headers.get("X-XSS-Protection") == "1; mode=block"


def test_cors_restricted():
    r = client.options(
        "/docs",
        headers={
            "Origin": "https://app.mita.finance",
            "Access-Control-Request-Method": "GET",
        },
    )
    origin = r.headers.get("access-control-allow-origin")
    assert origin == "https://app.mita.finance"

import os
import sys
import types
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

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
    Message=None, Notification=None, send=lambda *a, **k: None
)
sys.modules["firebase_admin"] = dummy
sys.modules["firebase_admin.credentials"] = dummy.credentials
sys.modules["firebase_admin.firestore"] = dummy.firestore
sys.modules["firebase_admin.messaging"] = dummy.messaging

import app.api.iap.routes as iap
import app.api.transactions.routes as tr
from app.main import app


class DummyRateLimiter:
    def __init__(self, times=5, seconds=60):
        self.times = times
        self.counter = 0

    async def __call__(self, request):
        self.counter += 1
        if self.counter > self.times:
            from fastapi import HTTPException

            raise HTTPException(status_code=429, detail="Too Many Requests")


@pytest.fixture(autouse=True)
def _patch_limiter(monkeypatch):
    monkeypatch.setattr("app.core.limiter_setup.init_rate_limiter", lambda app: None)

    from fastapi_limiter.depends import FastAPILimiter, RateLimiter

    FastAPILimiter.redis = object()

    from fastapi import Request, Response

    async def fake_call(self, request: Request, response: Response):
        counter = getattr(self, "_counter", 0) + 1
        object.__setattr__(self, "_counter", counter)
        if counter > self.times:
            from fastapi import HTTPException

            raise HTTPException(status_code=429, detail="Too Many Requests")

    monkeypatch.setattr(RateLimiter, "__call__", fake_call, raising=False)

    yield
    app.dependency_overrides = {}


def test_receipt_rate_limit(monkeypatch):
    app.dependency_overrides[tr.get_current_user] = lambda: SimpleNamespace(id="u1")
    app.dependency_overrides[tr.get_db] = lambda: iter([None])
    monkeypatch.setattr(tr.OCRReceiptService, "process_image", lambda self, path: {})
    client = TestClient(app)
    file = {"file": ("r.jpg", b"data")}
    for _ in range(5):
        resp = client.post("/api/transactions/transactions/receipt", files=file)
        assert resp.status_code == 200
    resp = client.post("/api/transactions/transactions/receipt", files=file)
    assert resp.status_code == 429


def test_iap_validate_rate_limit(monkeypatch):
    app.dependency_overrides[iap.get_current_user] = lambda: SimpleNamespace(id="u1")
    app.dependency_overrides[iap.get_db] = lambda: iter([None])

    async def dummy_validate(*a, **k):
        return {"status": "invalid"}

    monkeypatch.setattr(iap, "validate_receipt", dummy_validate)
    client = TestClient(app)
    payload = {"receipt": "r", "platform": "ios"}
    for _ in range(5):
        resp = client.post("/api/iap/iap/validate", json=payload)
        assert resp.status_code == 200
    resp = client.post("/api/iap/iap/validate", json=payload)
    assert resp.status_code == 429

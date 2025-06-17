import os
import sys
import types
from types import SimpleNamespace

from fastapi.testclient import TestClient

os.environ.setdefault("FIREBASE_JSON", "{}")

dummy = types.ModuleType("firebase_admin")
dummy._apps = []
dummy.credentials = types.SimpleNamespace(ApplicationDefault=lambda: None)
dummy.initialize_app = lambda cred=None: None
dummy.firestore = types.SimpleNamespace(
    client=lambda: types.SimpleNamespace(collection=lambda *a, **k: None)
)
dummy.messaging = types.SimpleNamespace(Message=None, Notification=None, send=lambda *a, **k: None)
sys.modules["firebase_admin"] = dummy
sys.modules["firebase_admin.credentials"] = dummy.credentials
sys.modules["firebase_admin.firestore"] = dummy.firestore
sys.modules["firebase_admin.messaging"] = dummy.messaging

from app.main import app
import app.api.insights.routes as insights_routes


class DummyQuery:
    def __init__(self, item):
        self.item = item

    def filter(self, *a, **k):
        return self

    def order_by(self, *a, **k):
        return self

    def first(self):
        return self.item

    def all(self):
        return [self.item] if self.item else []


class DummyDB:
    def __init__(self, item):
        self.item = item

    def query(self, model):
        return DummyQuery(self.item)


def test_latest_insight(monkeypatch):
    advice = {"id": "a1", "date": "2025-01-01", "type": "risk", "text": "be careful"}

    def dummy_get_db():
        yield DummyDB(advice)

    app.dependency_overrides[insights_routes.get_db] = dummy_get_db
    app.dependency_overrides[insights_routes.get_current_user] = lambda: SimpleNamespace(id="u1")

    client = TestClient(app)
    resp = client.get("/api/insights/")
    app.dependency_overrides = {}
    assert resp.status_code == 200
    assert resp.json()["data"]["text"] == "be careful"


def test_insight_history(monkeypatch):
    advice = {"id": "a1", "date": "2025-01-01", "type": "risk", "text": "be careful"}

    def dummy_get_db():
        yield DummyDB(advice)

    app.dependency_overrides[insights_routes.get_db] = dummy_get_db
    app.dependency_overrides[insights_routes.get_current_user] = lambda: SimpleNamespace(id="u1")

    client = TestClient(app)
    resp = client.get("/api/insights/history")
    app.dependency_overrides = {}
    assert resp.status_code == 200
    assert resp.json()["data"][0]["id"] == "a1"

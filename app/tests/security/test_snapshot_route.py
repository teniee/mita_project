import datetime
import time
import types
from types import SimpleNamespace

import pytest

from app.api.ai import routes as ai_routes
from app.services import auth_jwt_service as svc


class DummyDB:
    def __init__(self, snap=None):
        self.snap = snap
        self.rows = [snap] if snap else []

    def query(self, model):
        return self

    def filter_by(self, **kw):
        return self

    def order_by(self, *a, **k):
        return self

    def offset(self, n):
        self.rows = self.rows[n:]
        return self

    def limit(self, n):
        self.rows = self.rows[:n]
        return self

    def all(self):
        return self.rows


@pytest.mark.asyncio
async def test_snapshot_access_after_logout(monkeypatch):
    store = {}
    monkeypatch.setattr(
        svc, "upstash_blacklist_token", lambda jti, ttl: store.setdefault("jti", jti)
    )
    monkeypatch.setattr(
        svc, "is_token_blacklisted", lambda jti: jti == store.get("jti")
    )
    token = svc.create_access_token({"sub": "u1", "exp": time.time() + 60})
    user = SimpleNamespace(id="u1")

    db = DummyDB(
        types.SimpleNamespace(
            rating=1, risk=1, summary="s", created_at=datetime.datetime.utcnow()
        )
    )

    resp = await ai_routes.get_latest_ai_snapshots(user=user, db=db)
    assert resp["count"] == 1

    svc.blacklist_token(token)
    assert svc.verify_token(token) is None


@pytest.mark.asyncio
async def test_snapshot_pagination(monkeypatch):
    rows = [
        types.SimpleNamespace(
            rating=i,
            risk=i,
            summary=str(i),
            created_at=datetime.datetime.utcnow(),
        )
        for i in range(20)
    ]

    class DB:
        def query(self, model):
            return self

        def filter_by(self, **kw):
            return self

        def order_by(self, *a, **k):
            return self

        def offset(self, n):
            self.rows = rows[n:]
            return self

        def limit(self, n):
            self.rows = self.rows[:n]
            return self

        def all(self):
            return self.rows

    db = DB()
    user = SimpleNamespace(id="u1")
    resp = await ai_routes.get_latest_ai_snapshots(limit=5, offset=5, user=user, db=db)
    assert resp["count"] == 5

import datetime
import json
import time
import types
from types import SimpleNamespace

import pytest

from app.api.ai import routes as ai_routes
from app.services import auth_jwt_service as svc


class DummyDB:
    def __init__(self, snap=None):
        self.snap = snap

    def query(self, model):
        return self

    def filter_by(self, **kw):
        return self

    def order_by(self, *a, **k):
        return self

    def first(self):
        return self.snap


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
    data = json.loads(resp.body.decode())
    assert data["data"]["count"] == 1

    svc.blacklist_token(token)
    assert svc.verify_token(token) is None

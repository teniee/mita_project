import datetime
import json
import types
from types import SimpleNamespace

import pytest

from app.api.ai import routes as ai_routes
from app.services import auth_jwt_service as svc


class DummyResult:
    def __init__(self, snap):
        self._snap = snap

    def scalars(self):
        return self

    def first(self):
        return self._snap


class DummyAsyncDB:
    def __init__(self, snap=None):
        self.snap = snap

    async def execute(self, query):
        return DummyResult(self.snap)


class FakeBlacklistService:
    """In-memory stand-in for the Redis-backed token blacklist."""

    def __init__(self):
        self.jtis = set()

    async def is_token_blacklisted(self, jti: str) -> bool:
        return jti in self.jtis


@pytest.mark.asyncio
async def test_snapshot_access_after_logout(monkeypatch):
    fake_blacklist = FakeBlacklistService()

    async def fake_get_service():
        return fake_blacklist

    # verify_token resolves the blacklist service lazily from this module
    monkeypatch.setattr(
        "app.services.token_blacklist_service.get_blacklist_service",
        fake_get_service,
    )

    token = svc.create_access_token({"sub": "u1"})

    # Token valid before logout
    payload = await svc.verify_token(token)
    assert payload is not None and payload["sub"] == "u1"

    # Snapshot endpoint works while logged in
    user = SimpleNamespace(id="u1")
    db = DummyAsyncDB(
        types.SimpleNamespace(
            rating=1,
            risk=1,
            summary="s",
            created_at=datetime.datetime.now(datetime.timezone.utc),
        )
    )
    resp = await ai_routes.get_latest_ai_snapshots(user=user, db=db)
    data = json.loads(resp.body.decode())
    assert data["data"]["count"] == 1

    # Simulate logout: blacklist the token's jti — verification must now fail
    fake_blacklist.jtis.add(payload["jti"])
    assert await svc.verify_token(token) is None

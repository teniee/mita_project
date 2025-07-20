import time
from types import SimpleNamespace
import pytest
from app.services import auth_jwt_service as svc
from app.api.auth import routes as auth_routes

@pytest.mark.asyncio
async def test_logout_revokes_token(monkeypatch):
    store = {}
    monkeypatch.setattr(svc, "upstash_blacklist_token", lambda jti, ttl: store.setdefault("jti", jti))
    monkeypatch.setattr(svc, "is_token_blacklisted", lambda jti: jti == store.get("jti"))

    token = svc.create_access_token({"sub": "u1", "exp": time.time() + 60})
    assert svc.verify_token(token)

    svc.blacklist_token(token)
    assert svc.verify_token(token) is None


@pytest.mark.asyncio
async def test_refresh_revokes_old(monkeypatch):
    store = {}
    monkeypatch.setattr(svc, "upstash_blacklist_token", lambda jti, ttl: store.setdefault("jti", jti))
    monkeypatch.setattr(svc, "is_token_blacklisted", lambda jti: jti == store.get("jti"))

    refresh = svc.create_refresh_token({"sub": "u1", "exp": time.time() + 2})
    req = SimpleNamespace(headers={"Authorization": f"Bearer {refresh}"})
    resp = await auth_routes.refresh_token(req)
    assert "refresh_token" in resp
    assert svc.verify_token(refresh, "refresh_token") is None

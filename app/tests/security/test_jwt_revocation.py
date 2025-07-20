import time
import pytest
from app.services import auth_jwt_service as svc

@pytest.mark.asyncio
async def test_logout_revokes_token(monkeypatch):
    store = {}
    monkeypatch.setattr(svc, "upstash_blacklist_token", lambda jti, ttl: store.setdefault("jti", jti))
    monkeypatch.setattr(svc, "is_token_blacklisted", lambda jti: jti == store.get("jti"))

    token = svc.create_access_token({"sub": "u1", "exp": time.time() + 60})
    assert svc.verify_token(token)

    svc.blacklist_token(token)
    assert svc.verify_token(token) is None

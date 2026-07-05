import jwt
import pytest

from app.services import auth_jwt_service as svc


@pytest.mark.asyncio
async def test_verify_token_with_previous_secret(monkeypatch):
    """Tokens signed with JWT_PREVIOUS_SECRET must still verify after rotation."""
    monkeypatch.setattr(svc.settings, "SECRET_KEY", "new")
    monkeypatch.setattr(svc.settings, "JWT_PREVIOUS_SECRET", "old")
    token = jwt.encode(
        {
            "sub": "u1",
            "scope": "read:profile",
            "token_type": "access_token",
            "exp": 9999999999,
            "iss": svc.JWT_ISSUER,
            "aud": svc.JWT_AUDIENCE,
            "jti": "rotation-test-jti",
        },
        "old",
        algorithm=svc.ALGORITHM,
    )
    payload = await svc.verify_token(token)
    assert payload and payload["sub"] == "u1"


@pytest.mark.asyncio
async def test_verify_token_rejects_unknown_secret(monkeypatch):
    """Tokens signed with a secret that is neither current nor previous must fail."""
    monkeypatch.setattr(svc.settings, "SECRET_KEY", "new")
    monkeypatch.setattr(svc.settings, "JWT_PREVIOUS_SECRET", "old")
    token = jwt.encode(
        {
            "sub": "u1",
            "scope": "read:profile",
            "token_type": "access_token",
            "exp": 9999999999,
            "iss": svc.JWT_ISSUER,
            "aud": svc.JWT_AUDIENCE,
            "jti": "rotation-test-jti-2",
        },
        "neither",
        algorithm=svc.ALGORITHM,
    )
    payload = await svc.verify_token(token)
    assert payload is None

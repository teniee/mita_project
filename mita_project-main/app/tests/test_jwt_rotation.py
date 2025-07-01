from jose import jwt

from app.services import auth_jwt_service as svc


def test_verify_token_with_previous_secret(monkeypatch):
    monkeypatch.setattr(svc.settings, "SECRET_KEY", "new")
    monkeypatch.setattr(svc.settings, "JWT_PREVIOUS_SECRET", "old")
    token = jwt.encode(
        {"sub": "u1", "scope": "access_token", "exp": 9999999999},
        "old",
        algorithm=svc.ALGORITHM,
    )
    payload = svc.verify_token(token)
    assert payload and payload["sub"] == "u1"

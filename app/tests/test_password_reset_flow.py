"""Password-reset machinery regressions.

Two production-blocking defects are locked in here (found by the TASK-6
full-route contract suite, 2026-07-10):

1. PasswordResetTokenManager mixed the *generation* timestamp into the token
   hash, then verification recomputed the hash with the *verification*
   timestamp — so no reset token could EVER verify. The whole flow was
   cryptographically dead (masked until now by DEF-005: reset emails cannot
   send, so nobody reached confirm).
2. /api/auth/verify-reset-token (GET+POST, mobile-called) and
   /api/auth/reset-password imported a nonexistent
   auth_jwt_service.verify_password_reset_token and int()-cast UUID user ids
   — ImportError/ValueError -> 500 on every call.

Requires: PostgreSQL at DATABASE_URL (test_mita) with migrations at head.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db.models import User
from app.services.email_service import PasswordResetTokenManager


class TestTokenManagerRoundtrip:
    def test_generated_token_verifies(self):
        user_id = str(uuid4())
        token, token_hash = PasswordResetTokenManager.generate_reset_token(user_id)
        assert PasswordResetTokenManager.verify_reset_token(
            token, token_hash, user_id
        ), "a freshly generated token must verify against its stored hash"

    def test_wrong_token_rejected(self):
        user_id = str(uuid4())
        _, token_hash = PasswordResetTokenManager.generate_reset_token(user_id)
        assert not PasswordResetTokenManager.verify_reset_token(
            "not-the-token", token_hash, user_id
        )

    def test_token_bound_to_user(self):
        user_id = str(uuid4())
        token, token_hash = PasswordResetTokenManager.generate_reset_token(user_id)
        assert not PasswordResetTokenManager.verify_reset_token(
            token, token_hash, str(uuid4())
        ), "a token generated for user A must not verify for user B"


@pytest.fixture
def client():
    from app.main import app

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture
def db_session():
    import app.core.session as session_module

    gen = session_module.get_db()
    db = next(gen)
    try:
        yield db
    finally:
        gen.close()


@pytest.fixture
def reset_user(db_session):
    from app.services.auth_jwt_service import hash_password

    user = User(
        id=uuid4(),
        email=f"reset_{uuid4().hex[:10]}@mita.app",
        password_hash=hash_password("Old!passw0rd#2026"),
        has_onboarded=True,
        timezone="UTC",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    yield user
    db_session.query(User).filter_by(id=user.id).delete()
    db_session.commit()


def _arm_reset_token(db_session, user):
    """Simulate the /password-reset/request step: store the hash, return
    the plaintext token that would have been emailed."""
    token, token_hash = PasswordResetTokenManager.generate_reset_token(str(user.id))
    user.password_reset_token = token_hash
    user.password_reset_expires = datetime.now(timezone.utc) + timedelta(hours=2)
    db_session.commit()
    return token


class TestResetEndpoints:
    def test_verify_reset_token_roundtrip(self, client, db_session, reset_user):
        token = _arm_reset_token(db_session, reset_user)

        # GET variant (mobile-called) — was 500 (ImportError)
        r = client.get("/api/auth/verify-reset-token", params={"token": token})
        assert r.status_code == 200, r.text
        assert r.json()["data"]["valid"] is True

        # POST variant
        r = client.post("/api/auth/verify-reset-token", params={"token": token})
        assert r.status_code == 200, r.text
        assert r.json()["data"]["valid"] is True

        # Garbage token: clean invalid answer, not a 500
        r = client.get(
            "/api/auth/verify-reset-token", params={"token": "garbage-token"}
        )
        assert r.status_code == 200, r.text
        assert r.json()["data"]["valid"] is False

    def test_expired_token_reported_expired(self, client, db_session, reset_user):
        token = _arm_reset_token(db_session, reset_user)
        reset_user.password_reset_expires = datetime.now(timezone.utc) - timedelta(
            minutes=1
        )
        db_session.commit()

        r = client.get("/api/auth/verify-reset-token", params={"token": token})
        assert r.status_code == 200, r.text
        assert r.json()["data"]["valid"] is False

    def test_reset_password_end_to_end(self, client, db_session, reset_user):
        token = _arm_reset_token(db_session, reset_user)
        new_password = "New!passw0rd#2026"

        r = client.post(
            "/api/auth/reset-password",
            json={"token": token, "new_password": new_password},
        )
        assert r.status_code == 200, r.text

        # Token is cleared and single-use
        db_session.expire_all()
        assert reset_user.password_reset_token is None
        r = client.post(
            "/api/auth/reset-password",
            json={"token": token, "new_password": "Another!pass1#2026"},
        )
        assert 400 <= r.status_code < 500, r.text

        # The new password actually logs in; the old one is dead
        r = client.post(
            "/api/auth/login",
            json={"email": reset_user.email, "password": new_password},
        )
        assert r.status_code == 200, r.text
        r = client.post(
            "/api/auth/login",
            json={"email": reset_user.email, "password": "Old!passw0rd#2026"},
        )
        assert r.status_code == 401, r.text

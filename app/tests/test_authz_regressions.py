"""Authorization regressions.

- N-P2-IDOR-1: /api/goal/user-progress and /goal/state-progress accepted a
  body-supplied user_id without checking it against the session, letting
  authenticated user A trigger B-scoped reads. Identity must come from the
  session; a mismatched body user_id is a 403.
- N-P2-SECMON: /api/auth/security/status and /security/password-config were
  mounted with no auth at all and disclosed bcrypt configuration and security
  health to anonymous callers. They now require admin access.
"""

from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db.models import User


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
def user_a(db_session):
    user = User(
        id=uuid4(),
        email=f"authz_a_{uuid4().hex[:10]}@mita.app",
        password_hash="hashed_password_123",
        has_onboarded=True,
        timezone="UTC",
        monthly_income=Decimal("6000.00"),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    yield user
    db_session.query(User).filter_by(id=user.id).delete()
    db_session.commit()


@pytest.fixture
def as_user_a(client, user_a):
    from app.api.dependencies import get_current_user
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: user_a
    try:
        yield client
    finally:
        app.dependency_overrides.pop(get_current_user, None)


class TestGoalIdentityBinding:
    def test_user_progress_foreign_user_id_403(self, as_user_a):
        resp = as_user_a.post(
            "/api/goal/user-progress",
            json={"user_id": str(uuid4()), "year": 2026, "month": 7},
        )
        assert resp.status_code == 403, resp.text

    def test_user_progress_own_id_ok(self, as_user_a, user_a):
        resp = as_user_a.post(
            "/api/goal/user-progress",
            json={"user_id": str(user_a.id), "year": 2026, "month": 7},
        )
        assert resp.status_code == 200, resp.text

    def test_user_progress_no_user_id_uses_session(self, as_user_a):
        resp = as_user_a.post(
            "/api/goal/user-progress", json={"year": 2026, "month": 7}
        )
        assert resp.status_code == 200, resp.text

    def test_state_progress_foreign_user_id_403(self, as_user_a):
        resp = as_user_a.post(
            "/api/goal/state-progress",
            json={
                "user_id": str(uuid4()),
                "income": 5000,
                "fixed_expenses": 1500,
                "goal": 1000,
                "saved": 100,
            },
        )
        assert resp.status_code == 403, resp.text


class TestSecurityMonitoringAdminGate:
    def test_status_requires_auth(self, client):
        assert client.get("/api/auth/security/status").status_code in (401, 403)

    def test_password_config_requires_auth(self, client):
        assert client.get("/api/auth/security/password-config").status_code in (
            401,
            403,
        )

    def test_status_forbidden_for_non_admin(self, as_user_a):
        assert as_user_a.get("/api/auth/security/status").status_code == 403

    def test_password_config_forbidden_for_non_admin(self, as_user_a):
        assert as_user_a.get("/api/auth/security/password-config").status_code == 403

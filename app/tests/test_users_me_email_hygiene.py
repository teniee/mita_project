"""TASK-19 regressions: PATCH /api/users/me email-change hygiene.

- Changing the email must reset email_verified (the new address is unproven).
- Changing to an address another account owns must answer 409, not an
  IntegrityError 500.
- Re-submitting the CURRENT email must not drop the verified flag.

Requires: PostgreSQL at DATABASE_URL (test_mita) with migrations at head.
"""

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


def _make_user(db_session, verified=True):
    user = User(
        id=uuid4(),
        email=f"hygiene_{uuid4().hex[:10]}@mita.app",
        password_hash="hashed_password_123",
        has_onboarded=True,
        timezone="UTC",
        email_verified=verified,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def user_a(db_session):
    user = _make_user(db_session)
    yield user
    db_session.query(User).filter_by(id=user.id).delete()
    db_session.commit()


@pytest.fixture
def user_b(db_session):
    user = _make_user(db_session)
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


class TestEmailChangeHygiene:
    def test_email_change_resets_verified_flag(self, as_user_a, db_session, user_a):
        assert user_a.email_verified is True
        new_email = f"changed_{uuid4().hex[:10]}@mita.app"

        resp = as_user_a.patch("/api/users/me", json={"email": new_email})
        assert resp.status_code == 200, resp.text

        db_session.expire_all()
        assert user_a.email == new_email
        assert user_a.email_verified is False, (
            "a changed email address has not been verified and must not keep "
            "the verified flag"
        )

    def test_duplicate_email_is_409_not_500(
        self, as_user_a, db_session, user_a, user_b
    ):
        resp = as_user_a.patch("/api/users/me", json={"email": user_b.email})
        assert resp.status_code == 409, resp.text

        db_session.expire_all()
        assert user_a.email != user_b.email
        assert user_a.email_verified is True  # unchanged on rejection

    def test_same_email_keeps_verified_flag(self, as_user_a, db_session, user_a):
        resp = as_user_a.patch(
            "/api/users/me", json={"email": user_a.email, "name": "Same Email"}
        )
        assert resp.status_code == 200, resp.text

        db_session.expire_all()
        assert (
            user_a.email_verified is True
        ), "re-submitting the unchanged email must not drop verification"

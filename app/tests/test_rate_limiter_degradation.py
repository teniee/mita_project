"""Distributed-limiter outage must not 500 product routes.

Production incident (2026-07-11, Railway logs): REDIS_URL's host stopped
resolving, FastAPILimiter.init never ran, and every route carrying a raw
Depends(RateLimiter(...)) raised "You must call FastAPILimiter.init in
startup event of fastapi!" -> 500. That included the mobile-called
GET /transactions/budget-status and POST /transactions/check-affordability.

optional_rate_limit() must degrade OPEN (serve the request) when
FastAPILimiter has no Redis, and keep enforcing 429s when it does.

Requires: PostgreSQL at DATABASE_URL (test_mita) with migrations at head.
"""

from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db.models import DailyPlan, User


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
def user(db_session):
    u = User(
        id=uuid4(),
        email=f"limiter_{uuid4().hex[:10]}@mita.app",
        password_hash="hashed_password_123",
        has_onboarded=True,
        timezone="UTC",
        monthly_income=Decimal("6000.00"),
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    yield u
    db_session.query(DailyPlan).filter_by(user_id=u.id).delete()
    db_session.query(User).filter_by(id=u.id).delete()
    db_session.commit()


@pytest.fixture
def authed(client, user):
    from app.api.dependencies import get_current_user
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: user
    try:
        yield client
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def limiter_offline(monkeypatch):
    """Simulate the production condition: FastAPILimiter.init never ran."""
    from fastapi_limiter import FastAPILimiter

    monkeypatch.setattr(FastAPILimiter, "redis", None)


class TestDegradeOpen:
    def test_budget_status_serves_without_limiter(self, authed, limiter_offline):
        resp = authed.get("/api/transactions/budget-status")
        assert resp.status_code == 200, resp.text

    def test_check_affordability_serves_without_limiter(self, authed, limiter_offline):
        resp = authed.post(
            "/api/transactions/check-affordability",
            json={"category": "food", "amount": "15.00"},
        )
        assert resp.status_code == 200, resp.text

    def test_iap_validate_serves_without_limiter(self, authed, limiter_offline):
        resp = authed.post(
            "/api/iap/validate",
            json={"receipt": "degradation-test", "platform": "ios"},
        )
        # no store secret in test env -> wrapped invalid result, but 2xx
        assert resp.status_code == 200, resp.text


class TestStillEnforcedWhenLive:
    def test_429_when_limiter_is_live(self, authed):
        """With the local Redis-backed limiter initialized, hammering a
        tightly-limited route must still produce a 429 — degrading open must
        not mean never limiting."""
        from fastapi_limiter import FastAPILimiter

        if FastAPILimiter.redis is None:
            pytest.skip("local limiter not initialized")

        saw_429 = False
        for _ in range(8):  # /iap/validate allows 5/60s
            resp = authed.post(
                "/api/iap/validate",
                json={"receipt": "degradation-test", "platform": "ios"},
            )
            if resp.status_code == 429:
                saw_429 = True
                break
            assert resp.status_code == 200, resp.text
        assert saw_429, "limiter is live but never produced a 429"

"""Integration regressions for the systemic AsyncSession/sync-service bug
(adversarial-audit.md §2, N-P1-3 cases A–D).

Each of these endpoints injected AsyncSession and then called synchronous
SQLAlchemy code (db.query / sync db.execute(...).all() / awaiting a sync def),
raising on every request — either surfacing as HTTP 500 or being swallowed by
a broad except into a hardcoded fallback 200. These tests drive the REAL
routes through the real async DI and assert CONTENT, so the silent-fallback
failure mode cannot pass.

Requires: PostgreSQL at DATABASE_URL (test_mita) with migrations at head.
"""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db.models import AIAnalysisSnapshot, DailyPlan, Goal, Transaction, User


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
        email=f"sweep_{uuid4().hex[:10]}@mita.app",
        password_hash="hashed_password_123",
        has_onboarded=True,
        timezone="UTC",
        monthly_income=Decimal("6000.00"),
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    yield u
    for model in (AIAnalysisSnapshot, Transaction, DailyPlan, Goal):
        db_session.query(model).filter_by(user_id=u.id).delete()
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


def _seed_txn(db_session, user, amount, category="food"):
    txn = Transaction(
        user_id=user.id,
        category=category,
        amount=Decimal(amount),
        currency="USD",
        spent_at=datetime.now(timezone.utc),
    )
    db_session.add(txn)
    db_session.commit()
    return txn


class TestAnalyticsMonthlyTrend:
    """§2-B: /analytics/monthly and /trend awaited a sync def."""

    def test_monthly_returns_real_aggregation(self, authed, db_session, user):
        _seed_txn(db_session, user, "42.00", "food")
        _seed_txn(db_session, user, "10.00", "food")
        _seed_txn(db_session, user, "5.50", "transport")

        resp = authed.get("/api/analytics/monthly")
        assert resp.status_code == 200, resp.text
        categories = resp.json()["data"]["categories"]
        totals = {c["category"]: c["total"] for c in categories}
        assert totals["food"] == pytest.approx(52.00)
        assert totals["transport"] == pytest.approx(5.50)

    def test_trend_returns_daily_totals(self, authed, db_session, user):
        _seed_txn(db_session, user, "42.00")
        resp = authed.get("/api/analytics/trend")
        assert resp.status_code == 200, resp.text
        trend = resp.json()["data"]["trend"]
        today = datetime.now(timezone.utc).date().isoformat()
        today_points = [p for p in trend if p["date"] == today]
        assert today_points and today_points[0]["amount"] == pytest.approx(42.00)

    def test_monthly_excludes_soft_deleted(self, authed, db_session, user):
        _seed_txn(db_session, user, "10.00")
        gone = _seed_txn(db_session, user, "99.00")
        gone.deleted_at = datetime.now(timezone.utc)
        db_session.commit()

        resp = authed.get("/api/analytics/monthly")
        totals = {c["category"]: c["total"] for c in resp.json()["data"]["categories"]}
        assert totals["food"] == pytest.approx(10.00)


class TestAISnapshot:
    """§2-A: POST /ai/snapshot awaited the sync save_ai_snapshot."""

    def test_snapshot_persists_row(self, authed, db_session, user, monkeypatch):
        # The rating step calls OpenAI; stub it so the test exercises the
        # session plumbing and persistence, not the external API.
        import app.services.core.engine.ai_snapshot_service as snapshot_service

        monkeypatch.setattr(
            snapshot_service,
            "generate_financial_rating",
            lambda profile, db: {
                "rating": "B",
                "risk": "moderate",
                "summary": "stubbed",
            },
        )
        now = datetime.now(timezone.utc)
        resp = authed.post(
            "/api/ai/snapshot", params={"year": now.year, "month": now.month}
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["status"] == "saved"

        db_session.expire_all()
        rows = db_session.query(AIAnalysisSnapshot).filter_by(user_id=user.id).all()
        assert len(rows) == 1


class TestAIAnalyzerEndpoints:
    """§2-C: the analyzer endpoints must run the real analysis, not the
    swallowed-exception fallback."""

    def test_spending_patterns_not_fallback(self, authed, db_session, user):
        resp = authed.get("/api/ai/spending-patterns")
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        # The silent-fallback body carries an "error" marker — the real
        # analyzer result never does.
        assert "error" not in data, f"fallback served instead of analysis: {data}"

    def test_financial_health_score_runs(self, authed, db_session, user):
        _seed_txn(db_session, user, "42.00")
        resp = authed.get("/api/ai/financial-health-score")
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert "score" in data and "grade" in data


class TestGoalsBudgetIntegration:
    """§2-D + V4: /goals/budget/* 500'd; expenses summed with the wrong sign."""

    def test_allocate_returns_real_numbers(self, authed, db_session, user):
        _seed_txn(db_session, user, "100.00")
        goal = Goal(
            user_id=user.id,
            title="Emergency fund",
            target_amount=Decimal("1000.00"),
            monthly_contribution=Decimal("50.00"),
            status="active",
        )
        db_session.add(goal)
        db_session.commit()

        now = datetime.now(timezone.utc)
        resp = authed.get(
            "/api/goals/budget/allocate",
            params={"month": now.month, "year": now.year},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["monthly_income"] == pytest.approx(6000.00)
        # V4 regression: positive expenses must be counted (was always 0)
        assert data["existing_expenses"] == pytest.approx(100.00)
        assert data["available_for_goals"] == pytest.approx(5900.00)

    def test_adjustment_suggestions_not_500(self, authed):
        resp = authed.get("/api/goals/budget/adjustment_suggestions")
        assert resp.status_code == 200, resp.text
        assert "suggestions" in resp.json()["data"]

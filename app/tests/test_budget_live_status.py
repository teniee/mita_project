"""Regression: GET /api/budget/live_status must not 500 for an onboarded user.

There is one DailyPlan row per (day, category), so the endpoint's
scalar_one_or_none() raised MultipleResultsFound -> HTTP 500 on every
onboarded user, which broke the mobile dashboard (BudgetProvider treated the
5xx as fatal and showed "Unable to load dashboard"). The endpoint now
aggregates daily_budget/spent across today's category rows.

Requires: PostgreSQL at DATABASE_URL (test_mita) with migrations at head.
"""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db.models import DailyPlan, Transaction, User


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
        email=f"livestatus_{uuid4().hex[:10]}@mita.app",
        password_hash="x",
        has_onboarded=True,
        timezone="UTC",
        monthly_income=Decimal("6000.00"),
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    yield u
    db_session.query(Transaction).filter_by(user_id=u.id).delete()
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


def test_live_status_with_multiple_category_rows(authed, db_session, user):
    today = datetime.now(timezone.utc)
    # Multiple category rows for today — the shape that 500'd the old query.
    for cat, budget, spent in [
        ("food", "50.00", "12.00"),
        ("transport", "20.00", "0.00"),
        ("rent", "1500.00", "0.00"),
    ]:
        db_session.add(
            DailyPlan(
                id=uuid4(),
                user_id=user.id,
                date=today,
                category=cat,
                planned_amount=Decimal(budget),
                daily_budget=Decimal(budget),
                spent_amount=Decimal(spent),
                status="green",
            )
        )
    db_session.commit()

    resp = authed.get("/api/budget/live_status")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    # Aggregated across the three category rows.
    assert data["daily_budget"] == pytest.approx(1570.00)
    assert data["spent_today"] == pytest.approx(12.00)
    assert data["remaining_today"] == pytest.approx(1558.00)


def test_live_status_no_plan_rows(authed):
    # No daily_plan rows at all must still be 200 (neutral), not 500.
    resp = authed.get("/api/budget/live_status")
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["status"] == "neutral"

"""Regression: GET /api/budget/live_status must not 500 for an onboarded user.

There is one DailyPlan row per (day, category), so the endpoint's
scalar_one_or_none() raised MultipleResultsFound -> HTTP 500 on every
onboarded user, which broke the mobile dashboard (BudgetProvider treated the
5xx as fatal and showed "Unable to load dashboard"). The endpoint now
aggregates daily_budget/spent across today's category rows.

Requires: PostgreSQL at DATABASE_URL (test_mita) with migrations at head.
"""

from datetime import datetime
from datetime import time as dtime
from datetime import timedelta, timezone
from decimal import Decimal
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from app.db.models import DailyPlan, Transaction, User

SOFIA = ZoneInfo("Europe/Sofia")


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


def test_live_status_no_plan_rows(authed, db_session, user):
    # A user with genuinely nothing to plan from — no rows, and no income to
    # generate any — must still be 200 (neutral), not 500. This is the original
    # MultipleResultsFound regression and it stays covered.
    #
    # The precondition has to be set explicitly now: since the monthly rollover
    # fix, /budget/live_status calls ensure_month_plan, so an onboarded user WHO
    # HAS INCOME can no longer reach this endpoint with zero plan rows — that is
    # the point of the fix, and the next test pins it.
    user.monthly_income = Decimal("0.00")
    db_session.commit()

    resp = authed.get("/api/budget/live_status")
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["status"] == "neutral"
    assert resp.json()["data"]["daily_budget"] == pytest.approx(0.0)


def test_live_status_materializes_the_month_for_a_user_with_income(
    authed, db_session, user
):
    """The rollover fix, at this endpoint.

    Before it, an account whose plan month had rolled over reported
    daily_budget 0.0 / status "neutral" while the user had a real budget —
    indistinguishable from having no budget at all.
    """
    assert (
        db_session.query(DailyPlan).filter_by(user_id=user.id).count() == 0
    ), "precondition: the user starts with no plan rows"

    resp = authed.get("/api/budget/live_status")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]

    assert data["daily_budget"] > 0.0
    assert data["status"] != "neutral"

    db_session.expire_all()
    assert (
        db_session.query(DailyPlan).filter_by(user_id=user.id).count() > 0
    ), "the month must be persisted server-side, not computed per request"


def test_live_status_counts_only_active_month_to_date_transactions(
    authed, db_session, user
):
    now = datetime.now(timezone.utc)
    month_start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    if now - month_start <= timedelta(seconds=1):
        pytest.skip("suite is running at the exact UTC month boundary")
    current_month_instant = month_start + ((now - month_start) / 2)
    other_user = User(
        id=uuid4(),
        email=f"livestatus_other_{uuid4().hex[:10]}@mita.app",
        password_hash="x",
        has_onboarded=True,
        timezone="UTC",
        monthly_income=Decimal("6000.00"),
    )
    db_session.add(other_user)
    db_session.flush()
    db_session.add_all(
        [
            Transaction(
                id=uuid4(),
                user_id=user.id,
                amount=Decimal("11.00"),
                category="food",
                description="current active",
                spent_at=current_month_instant,
            ),
            Transaction(
                id=uuid4(),
                user_id=user.id,
                amount=Decimal("22.00"),
                category="food",
                description="current deleted",
                spent_at=current_month_instant,
                deleted_at=now,
            ),
            Transaction(
                id=uuid4(),
                user_id=user.id,
                amount=Decimal("33.00"),
                category="food",
                description="previous month",
                spent_at=month_start - timedelta(minutes=1),
            ),
            Transaction(
                id=uuid4(),
                user_id=user.id,
                amount=Decimal("44.00"),
                category="food",
                description="future transaction",
                spent_at=now + timedelta(hours=1),
            ),
            Transaction(
                id=uuid4(),
                user_id=other_user.id,
                amount=Decimal("55.00"),
                category="food",
                description="another user",
                spent_at=current_month_instant,
            ),
        ]
    )
    db_session.commit()

    try:
        resp = authed.get("/api/budget/live_status")
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["transaction_count"] == 1
        assert data["monthly_spent"] == pytest.approx(11.00)
    finally:
        db_session.query(Transaction).filter_by(user_id=other_user.id).delete()
        db_session.query(User).filter_by(id=other_user.id).delete()
        db_session.commit()


def test_live_status_count_uses_sofia_month_boundary(authed, db_session, user):
    now_local = datetime.now(SOFIA)
    local_month_start = datetime.combine(
        now_local.date().replace(day=1),
        dtime.min,
        tzinfo=SOFIA,
    )
    local_0030 = local_month_start + timedelta(minutes=30)
    if local_0030 >= now_local:
        pytest.skip("suite is running within 30 minutes of the local month start")

    user.timezone = "Europe/Sofia"
    db_session.add(
        Transaction(
            id=uuid4(),
            user_id=user.id,
            amount=Decimal("21.00"),
            category="food",
            description="Sofia month boundary",
            spent_at=local_0030.astimezone(timezone.utc),
        )
    )
    db_session.commit()

    resp = authed.get("/api/budget/live_status")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["transaction_count"] == 1
    assert data["monthly_spent"] == pytest.approx(21.00)


def test_remaining_and_spent_bridge_async_session(authed, db_session, user):
    """/budget/remaining and /budget/spent call sync BudgetTracker services;
    with the raw AsyncSession they 500'd on every dashboard load."""
    today = datetime.now(timezone.utc)
    db_session.add(
        DailyPlan(
            id=uuid4(),
            user_id=user.id,
            date=today,
            category="food",
            planned_amount=Decimal("50.00"),
            daily_budget=Decimal("50.00"),
            spent_amount=Decimal("12.00"),
            status="green",
        )
    )
    db_session.commit()

    assert authed.get("/api/budget/remaining").status_code == 200
    assert authed.get("/api/budget/spent").status_code == 200

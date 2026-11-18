"""F-9 and R3 through the real mobile routes.

* ``GET /api/budget/forecast`` reads the user's calendar day, not the server's
  UTC date: at 22:30 UTC on 31 October a user in Sofia (UTC+2) is in the first
  minutes of 1 November, so the default month is November with 29 days after
  today — the same as ChatGPT's ``get_budget_forecast``.
* It holds the month's unpaid bills out of the safe daily limit
  (``commitments_reserved``, owner decision 2026-10-25): a saved rent due on
  the 1st, not recorded, is held once even though the plan has it too.
* ``GET /api/budget/live_status`` leaves money set aside (savings, goal
  reservations) out of today's budget, as ChatGPT's ``get_budget_status.today``
  does (owner decision 2026-10-23).

Requires: PostgreSQL at DATABASE_URL (test_mita) with migrations at head.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db.models import DailyPlan, ScheduledExpense, Transaction, User

LATE = datetime(2026, 10, 31, 22, 30, tzinfo=timezone.utc)  # 00:30, 1 Nov, Sofia


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
        email=f"forecast_local_{uuid4().hex[:10]}@mita.app",
        password_hash="x",
        has_onboarded=True,
        timezone="Europe/Sofia",
        monthly_income=Decimal("3000.00"),
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    yield u
    db_session.query(ScheduledExpense).filter_by(user_id=u.id).delete()
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


def _row(user, day: date, category: str, amount: str) -> DailyPlan:
    stored = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    return DailyPlan(
        id=uuid4(),
        user_id=user.id,
        date=stored,
        category=category,
        planned_amount=Decimal(amount),
        daily_budget=Decimal(amount),
        spent_amount=Decimal("0.00"),
        status="green",
    )


def test_forecast_reads_the_user_s_month_and_holds_the_unpaid_rent(
    authed, db_session, user, monkeypatch
):
    """November: rent 800.00 on the 1st and groceries 10.00 a day (1,100.00),
    a saved monthly rent due on 1 November, nothing recorded.
    (1,100.00 - 0.00 spent - 800.00 held) / 29 days = 10.34."""
    import app.api.budget.routes as routes

    class Frozen(datetime):
        @classmethod
        def now(cls, tz=None):
            return LATE if tz else LATE.replace(tzinfo=None)

    monkeypatch.setattr(routes, "datetime", Frozen)
    for day in range(1, 31):
        db_session.add(_row(user, date(2026, 11, day), "groceries", "10.00"))
    db_session.add(_row(user, date(2026, 11, 1), "rent", "800.00"))
    db_session.add(
        ScheduledExpense(
            id=uuid4(),
            user_id=user.id,
            category="rent",
            amount=Decimal("800.00"),
            scheduled_date=date(2026, 11, 1),
            recurrence="monthly",
            status="pending",
        )
    )
    db_session.commit()

    resp = authed.get("/api/budget/forecast")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert (data["year"], data["month"], data["days_remaining"]) == (2026, 11, 29)
    assert data["total_planned"] == pytest.approx(1100.00)
    assert data["commitments_reserved"] == pytest.approx(800.00)
    assert data["safe_daily_limit"] == pytest.approx(10.34)


def test_a_bill_paid_in_the_app_is_not_held_twice(
    authed, db_session, user, monkeypatch
):
    """The same November, the rent paid in the app on 1 November (800.00,
    recorded through the ledger). The app cannot link an expense to a saved
    payment (only ChatGPT can, ``obligation_payments``), so here what is
    recorded on the rent line settles it (R3's rule): nothing is held, and
    (1,100.00 - 800.00 spent) / 29 days = 10.34 — the payment is counted
    once. Holding the 800.00 again, as 2.7.0's linked-only rule did on this
    surface, gave (1,100.00 - 800.00 - 800.00) / 29 = -17.24 (PR #288 review
    G0-01)."""
    import app.api.budget.routes as routes
    from app.services.core.engine.expense_tracker import rebuild_month_plan

    class Frozen(datetime):
        @classmethod
        def now(cls, tz=None):
            return LATE if tz else LATE.replace(tzinfo=None)

    monkeypatch.setattr(routes, "datetime", Frozen)
    for day in range(1, 31):
        db_session.add(_row(user, date(2026, 11, day), "groceries", "10.00"))
    db_session.add(_row(user, date(2026, 11, 1), "rent", "800.00"))
    db_session.add(
        ScheduledExpense(
            id=uuid4(),
            user_id=user.id,
            category="rent",
            amount=Decimal("800.00"),
            scheduled_date=date(2026, 11, 1),
            recurrence="monthly",
            status="pending",
        )
    )
    db_session.add(
        Transaction(
            id=uuid4(),
            user_id=user.id,
            category="rent",
            amount=Decimal("800.00"),
            currency="USD",
            spent_at=datetime(2026, 10, 31, 22, 10, tzinfo=timezone.utc),
        )
    )
    db_session.commit()
    rebuild_month_plan(db_session, user.id, date(2026, 11, 1), tz=user.timezone)

    resp = authed.get("/api/budget/forecast")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["total_spent"] == pytest.approx(800.00)
    assert data["commitments_reserved"] == pytest.approx(0.00)
    assert data["safe_daily_limit"] == pytest.approx(10.34)


NOV_20 = datetime(2026, 11, 20, 10, 0, tzinfo=timezone.utc)  # 12:00, 20 Nov, Sofia


def _at_nov_20(monkeypatch):
    import app.api.budget.routes as routes

    class Frozen(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOV_20 if tz else NOV_20.replace(tzinfo=None)

    monkeypatch.setattr(routes, "datetime", Frozen)


def _spent(db_session, user, category: str, amount: str, day: int) -> None:
    db_session.add(
        Transaction(
            id=uuid4(),
            user_id=user.id,
            category=category,
            amount=Decimal(amount),
            currency="USD",
            spent_at=datetime(2026, 11, day, 10, tzinfo=timezone.utc),
        )
    )


def test_fuel_never_releases_a_car_loan_scheduled_in_the_app(
    authed, db_session, user, monkeypatch
):
    """Independent review, finding 1 (P0), through the real routes.

    November: groceries 10.00 a day and transport 5.00 a day (450.00). The
    user schedules a 270.00 car loan for 25 November in the app and buys
    150.00 of fuel. The loan is unpaid, so it stays held in full:
    (450.00 − 150.00 − 270.00) / 10 days after today = 3.00 a day. Before
    the fix, the fuel released 150.00 of it: 120.00 held, 18.00 a day."""
    from app.services.core.engine.expense_tracker import rebuild_month_plan

    _at_nov_20(monkeypatch)
    for day in range(1, 31):
        db_session.add(_row(user, date(2026, 11, day), "groceries", "10.00"))
        db_session.add(_row(user, date(2026, 11, day), "transportation", "5.00"))
    db_session.commit()
    created = authed.post(
        "/api/scheduled-expenses/",
        json={
            "category": "transportation",
            "amount": "270.00",
            "scheduled_date": "2026-11-25",
            "merchant": "Car loan",
            "recurrence": "monthly",
        },
    )
    assert created.status_code == 200, created.text
    for day in range(1, 11):
        _spent(db_session, user, "transportation", "15.00", day)
    db_session.commit()
    rebuild_month_plan(db_session, user.id, date(2026, 11, 1), tz=user.timezone)

    data = authed.get("/api/budget/forecast").json()["data"]
    assert data["total_spent"] == pytest.approx(150.00)
    assert data["commitments_reserved"] == pytest.approx(270.00)
    assert data["safe_daily_limit"] == pytest.approx(3.00)


def test_a_lamp_never_releases_a_laptop_loan(authed, db_session, user, monkeypatch):
    """Finding 1, second case: groceries 10.00 a day, a 70.00 laptop loan for
    25 November scheduled in the app under 'other' (no other 'other' money),
    a 70.00 lamp also recorded as 'other'. The loan stays held:
    (300.00 − 70.00 − 70.00) / 10 = 16.00 a day."""
    from app.services.core.engine.expense_tracker import rebuild_month_plan

    _at_nov_20(monkeypatch)
    for day in range(1, 31):
        db_session.add(_row(user, date(2026, 11, day), "groceries", "10.00"))
    db_session.commit()
    created = authed.post(
        "/api/scheduled-expenses/",
        json={
            "category": "other",
            "amount": "70.00",
            "scheduled_date": "2026-11-25",
            "merchant": "Laptop loan",
            "recurrence": "monthly",
        },
    )
    assert created.status_code == 200, created.text
    _spent(db_session, user, "other", "70.00", 12)
    db_session.commit()
    rebuild_month_plan(db_session, user.id, date(2026, 11, 1), tz=user.timezone)

    data = authed.get("/api/budget/forecast").json()["data"]
    assert data["commitments_reserved"] == pytest.approx(70.00)
    assert data["safe_daily_limit"] == pytest.approx(16.00)


def test_the_app_s_create_route_writes_origin_app(authed, db_session, user):
    """The one writer of "app", the only origin the legacy processor acts on
    (migration 0045)."""
    created = authed.post(
        "/api/scheduled-expenses/",
        json={
            "category": "rent",
            "amount": "500.00",
            "scheduled_date": "2099-01-31",
            "recurrence": "monthly",
        },
    )
    assert created.status_code == 200, created.text
    db_session.expire_all()
    row = db_session.query(ScheduledExpense).filter_by(user_id=user.id).one()
    assert (row.origin, row.day_of_month) == ("app", None)


def test_live_status_leaves_today_s_money_set_aside_out(authed, db_session, user):
    """Today: groceries 10.00, Savings 10.00, a goal reservation 5.00. The
    day's spending budget is the groceries' 10.00."""
    from app.services.core.engine.expense_tracker import local_day_of

    today = local_day_of(datetime.now(timezone.utc), user.timezone)
    for category, amount in (
        ("groceries", "10.00"),
        ("savings goal based", "10.00"),
        ("goal_savings", "5.00"),
    ):
        db_session.add(_row(user, today, category, amount))
    db_session.commit()

    resp = authed.get("/api/budget/live_status")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["daily_budget"] == pytest.approx(10.00)
    assert data["remaining_today"] == pytest.approx(10.00)

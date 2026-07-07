"""
Regression tests: calendar day limits must be real, non-zero budgets.

Bug context (closed-beta readiness audit):
- `save_calendar_for_user` wrote `planned_amount` but never `daily_budget`,
  so every day returned by GET /api/calendar/saved/{year}/{month} had
  `"limit": 0.0`. The mobile calendar's traffic-light and safe-to-spend
  features silently degraded for every onboarded user.
- The transaction path (`apply_transaction_to_plan`) and the realtime
  rebalancer mutated `planned_amount` without touching `daily_budget`,
  letting the enforceable limit drift from the allocation.
- The saved-calendar route emitted full timestamps ("2026-07-06T00:00:00+00:00")
  instead of the YYYY-MM-DD day keys the mobile app merges on.

Invariant under test: wherever an allocation is written or moved,
`daily_budget` follows `planned_amount`; the API day limit is never 0 for a
planned day; legacy NULL-daily_budget rows fall back to the planned total.
"""

from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db.models import DailyPlan, Transaction, User


@pytest.fixture
def client():
    from app.main import app

    return TestClient(app, raise_server_exceptions=False)


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
def test_user(db_session):
    user = User(
        id=uuid4(),
        email=f"cal_limits_{uuid4().hex[:8]}@mita.app",
        password_hash="hashed_password_123",
        has_onboarded=True,
        monthly_income=Decimal("5000.00"),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    yield user
    db_session.query(Transaction).filter_by(user_id=user.id).delete()
    db_session.query(DailyPlan).filter_by(user_id=user.id).delete()
    db_session.query(User).filter_by(id=user.id).delete()
    db_session.commit()


class TestCalendarWritersSetDailyBudget:
    """Service level: every DailyPlan writer keeps daily_budget == planned_amount."""

    def test_save_calendar_sets_daily_budget(self, db_session, test_user):
        from app.services.calendar_service_real import save_calendar_for_user

        save_calendar_for_user(
            db_session,
            test_user.id,
            {"2026-08-01": {"food": 42.50, "transport": 10.00}},
        )

        rows = db_session.query(DailyPlan).filter_by(user_id=test_user.id).all()
        assert len(rows) == 2
        for row in rows:
            assert (
                row.daily_budget is not None
            ), f"{row.category}: daily_budget must be written at save time"
            assert row.daily_budget == row.planned_amount

    def test_update_day_entry_syncs_daily_budget(self, db_session, test_user):
        from app.services.calendar_service_real import (
            save_calendar_for_user,
            update_day_entry,
        )

        save_calendar_for_user(
            db_session, test_user.id, {"2026-08-02": {"food": 20.00}}
        )
        # Update existing category and insert a brand-new one.
        update_day_entry(
            db_session,
            test_user.id,
            date(2026, 8, 2),
            {"food": 35.00, "entertainment": 15.00},
        )

        rows = db_session.query(DailyPlan).filter_by(user_id=test_user.id).all()
        by_cat = {r.category: r for r in rows}
        assert by_cat["food"].planned_amount == Decimal("35.00")
        assert by_cat["food"].daily_budget == Decimal("35.00")
        assert by_cat["entertainment"].daily_budget == Decimal("15.00")

    def test_transaction_created_plan_row_has_explicit_zero_budget(
        self, db_session, test_user
    ):
        """An unplanned-category spend creates a row with budget 0, never NULL."""
        from app.services.core.engine.expense_tracker import apply_transaction_to_plan

        txn = Transaction(
            user_id=test_user.id,
            category="gadgets",
            amount=Decimal("12.34"),
            currency="USD",
            spent_at=datetime(2026, 8, 3, 12, 0, 0),
        )
        db_session.add(txn)
        db_session.commit()
        db_session.refresh(txn)

        apply_transaction_to_plan(db_session, txn)

        row = (
            db_session.query(DailyPlan)
            .filter_by(user_id=test_user.id, category="gadgets")
            .one()
        )
        assert row.spent_amount == Decimal("12.34")
        assert row.daily_budget is not None
        assert row.daily_budget == Decimal("0.00")

    def test_rebalance_keeps_daily_budget_in_sync(self, db_session, test_user):
        """Donor cuts and overspend credits both move the enforceable limit."""
        from app.services.calendar_service_real import save_calendar_for_user
        from app.services.core.engine.realtime_rebalancer import (
            rebalance_after_overspend,
        )

        save_calendar_for_user(
            db_session,
            test_user.id,
            {
                "2026-08-10": {"food": 10.00},
                "2026-08-11": {"entertainment": 40.00},
                "2026-08-12": {"entertainment": 40.00},
            },
        )
        # Overspend food on the 10th so the rebalancer pulls from future
        # entertainment days and credits the food row back.
        food_row = (
            db_session.query(DailyPlan)
            .filter_by(user_id=test_user.id, category="food")
            .one()
        )
        food_row.spent_amount = Decimal("30.00")
        db_session.commit()

        result = rebalance_after_overspend(
            db_session,
            test_user.id,
            overspent_category="food",
            overspend_amount=Decimal("20.00"),
            transaction_date=date(2026, 8, 10),
        )
        assert result.covered > Decimal("0"), "rebalance should find donors"

        rows = db_session.query(DailyPlan).filter_by(user_id=test_user.id).all()
        for row in rows:
            assert row.daily_budget == row.planned_amount, (
                f"{row.category} {row.date}: limit drifted from allocation "
                f"(planned={row.planned_amount}, budget={row.daily_budget})"
            )


class TestSavedCalendarRouteLimits:
    """API route level: /api/calendar/saved/{year}/{month} day contract."""

    @pytest.fixture
    def auth_client(self, client, test_user):
        from app.api.dependencies import get_current_user
        from app.main import app

        app.dependency_overrides[get_current_user] = lambda: test_user
        try:
            yield client
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    def test_saved_calendar_days_have_nonzero_limits(
        self, auth_client, db_session, test_user
    ):
        from app.services.calendar_service_real import save_calendar_for_user

        save_calendar_for_user(
            db_session,
            test_user.id,
            {
                "2026-08-01": {"food": 42.50, "transport": 10.00},
                "2026-08-02": {"food": 42.50},
            },
        )

        resp = auth_client.get("/api/calendar/saved/2026/8")
        assert resp.status_code == 200
        days = resp.json()["data"]["calendar"]
        assert len(days) == 2
        for day in days:
            assert day["limit"] > 0, f"day {day['date']} has zero limit"
        by_date = {d["date"]: d for d in days}
        assert by_date["2026-08-01"]["limit"] == pytest.approx(52.50)
        assert by_date["2026-08-02"]["limit"] == pytest.approx(42.50)

    def test_saved_calendar_dates_are_plain_day_keys(
        self, auth_client, db_session, test_user
    ):
        """Mobile merges calendar and transactions on YYYY-MM-DD keys."""
        from app.services.calendar_service_real import save_calendar_for_user

        save_calendar_for_user(
            db_session, test_user.id, {"2026-08-05": {"food": 30.00}}
        )

        resp = auth_client.get("/api/calendar/saved/2026/8")
        assert resp.status_code == 200
        days = resp.json()["data"]["calendar"]
        assert days, "calendar must not be empty"
        for day in days:
            assert (
                "T" not in day["date"]
            ), f"date must be YYYY-MM-DD, got {day['date']!r}"
        assert days[0]["date"] == "2026-08-05"
        assert days[0]["day"] == 5

    def test_legacy_rows_without_daily_budget_fall_back_to_planned(
        self, auth_client, db_session, test_user
    ):
        """Rows written before daily_budget existed must still show a limit."""
        db_session.add(
            DailyPlan(
                id=uuid4(),
                user_id=test_user.id,
                date=datetime(2026, 8, 20),
                category="food",
                planned_amount=Decimal("25.00"),
                daily_budget=None,
                spent_amount=Decimal("5.00"),
            )
        )
        db_session.commit()

        resp = auth_client.get("/api/calendar/saved/2026/8")
        assert resp.status_code == 200
        days = resp.json()["data"]["calendar"]
        assert len(days) == 1
        assert days[0]["limit"] == pytest.approx(25.00)
        assert days[0]["spent"] == pytest.approx(5.00)
        assert days[0]["status"] == "active"

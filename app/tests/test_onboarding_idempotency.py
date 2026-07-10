"""Regressions for INV-16 / TASK-3: daily_plan uniqueness + onboarding idempotency.

Before this fix:
- daily_plan had no UNIQUE(user_id, date, category);
- save_calendar_for_user appended a full new set of rows on every call;
- POST /onboarding/submit had no idempotency guard, so a mobile retry
  duplicated every plan row and the .first()-based spend accrual silently
  split spending across duplicates.

Requires: PostgreSQL at DATABASE_URL (test_mita) with migrations at head
(0035 adds the constraint).
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.db.models import DailyPlan, Transaction, User
from app.services.calendar_service_real import save_calendar_for_user


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
        email=f"onb_idem_{uuid4().hex[:10]}@mita.app",
        password_hash="hashed_password_123",
        has_onboarded=False,
        timezone="UTC",
        monthly_income=Decimal("0.00"),
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    yield u
    db_session.rollback()
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


ONBOARDING_BODY = {
    "income": {"monthly_income": 6000.0, "additional_income": 0.0},
    "fixed_expenses": {"rent": 1500.0, "utilities": 200.0},
    "spending_habits": {"dining_out_per_month": 8},
    "goals": {"savings_goal_amount_per_month": 400.0},
    "region": "US-CA",
}


def _plan_rows(db_session, user):
    db_session.expire_all()
    return db_session.query(DailyPlan).filter_by(user_id=user.id).all()


def _dupe_key_counts(rows):
    counts = {}
    for r in rows:
        day = r.date.date() if hasattr(r.date, "date") else r.date
        key = (day, r.category)
        counts[key] = counts.get(key, 0) + 1
    return counts


class TestOnboardingIdempotency:
    def test_resubmit_does_not_duplicate_plan(self, authed, db_session, user):
        r1 = authed.post("/api/onboarding/submit", json=ONBOARDING_BODY)
        assert r1.status_code == 200, r1.text

        rows_after_first = _plan_rows(db_session, user)
        assert rows_after_first, "first submit must create plan rows"
        count_first = len(rows_after_first)

        # Mobile retry / double-tap: identical request again
        r2 = authed.post("/api/onboarding/submit", json=ONBOARDING_BODY)
        assert r2.status_code == 200, r2.text
        assert r2.json()["data"]["status"] == "already_onboarded"

        rows_after_second = _plan_rows(db_session, user)
        assert len(rows_after_second) == count_first
        assert all(c == 1 for c in _dupe_key_counts(rows_after_second).values())

    def test_spend_accrues_once_after_resubmit(self, authed, db_session, user):
        assert (
            authed.post("/api/onboarding/submit", json=ONBOARDING_BODY).status_code
            == 200
        )
        authed.post("/api/onboarding/submit", json=ONBOARDING_BODY)

        # Spend 42 in food today; exactly one plan row must carry it
        resp = authed.post(
            "/api/transactions/",
            json={
                "amount": 42.00,
                "category": "food",
                "description": "idempotency spend",
                "spent_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        assert resp.status_code in (200, 201), resp.text

        today = datetime.now(timezone.utc).date()
        rows = [
            r
            for r in _plan_rows(db_session, user)
            if (r.date.date() if hasattr(r.date, "date") else r.date) == today
            and r.category == "food"
        ]
        assert len(rows) == 1
        assert Decimal(rows[0].spent_amount).quantize(Decimal("0.01")) == Decimal(
            "42.00"
        )


class TestSaveCalendarUpsert:
    CAL_V1 = {"2026-08-01": {"food": 50.0, "transport": 20.0}}
    CAL_V2 = {"2026-08-01": {"food": 75.0, "transport": 20.0}}

    def test_double_save_no_duplicates(self, db_session, user):
        save_calendar_for_user(db_session, user.id, self.CAL_V1)
        save_calendar_for_user(db_session, user.id, self.CAL_V1)

        rows = _plan_rows(db_session, user)
        assert len(rows) == 2
        assert all(c == 1 for c in _dupe_key_counts(rows).values())

    def test_upsert_updates_planned_preserves_spent(self, db_session, user):
        save_calendar_for_user(db_session, user.id, self.CAL_V1)

        food = (
            db_session.query(DailyPlan)
            .filter_by(user_id=user.id, category="food")
            .one()
        )
        food.spent_amount = Decimal("12.34")
        db_session.commit()

        save_calendar_for_user(db_session, user.id, self.CAL_V2)

        db_session.expire_all()
        food = (
            db_session.query(DailyPlan)
            .filter_by(user_id=user.id, category="food")
            .one()  # .one() also asserts no duplicate row
        )
        assert Decimal(food.planned_amount) == Decimal("75.00")
        assert Decimal(food.daily_budget) == Decimal("75.00")
        assert Decimal(food.spent_amount) == Decimal("12.34")

    def test_db_constraint_blocks_raw_duplicates(self, db_session, user):
        day = date(2026, 8, 2)
        db_session.add(
            DailyPlan(
                id=uuid4(),
                user_id=user.id,
                date=day,
                category="food",
                planned_amount=Decimal("10.00"),
                daily_budget=Decimal("10.00"),
                spent_amount=Decimal("0.00"),
            )
        )
        db_session.commit()

        db_session.add(
            DailyPlan(
                id=uuid4(),
                user_id=user.id,
                date=day,
                category="food",
                planned_amount=Decimal("10.00"),
                daily_budget=Decimal("10.00"),
                spent_amount=Decimal("0.00"),
            )
        )
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

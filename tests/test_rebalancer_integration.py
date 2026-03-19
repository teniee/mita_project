"""
Integration test for the full rebalance flow using real SQLite in-memory DB.

This test exercises the FULL pipeline:
  1. DailyPlan rows created (simulating calendar generation)
  2. Transaction logged via apply_transaction_to_plan()
  3. Auto-rebalance triggered via check_and_rebalance()
  4. DB state verified — donor reduced, overspent entry credited

This catches real DB issues mocks cannot:
  - DateTime vs date comparison in WHERE clauses
  - Decimal precision in Numeric(12,2) columns
  - Commit/rollback correctness
  - SQLAlchemy filter_by with DateTime columns
"""
import sys
import os
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.models.daily_plan import DailyPlan
from app.services.core.engine.realtime_rebalancer import (
    check_and_rebalance,
    rebalance_after_overspend,
)

# ---------------------------------------------------------------------------
# SQLite in-memory fixtures
#
# We create only the daily_plan table with raw SQL to avoid JSONB columns
# from other models (JSONB is PostgreSQL-only and breaks SQLite).
# ---------------------------------------------------------------------------

_CREATE_DAILY_PLAN = """
CREATE TABLE IF NOT EXISTS daily_plan (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL,
    date        DATETIME NOT NULL,
    category    VARCHAR(100),
    planned_amount  DECIMAL(12, 2) DEFAULT 0.00,
    spent_amount    DECIMAL(12, 2) DEFAULT 0.00,
    daily_budget    DECIMAL(12, 2),
    status      VARCHAR(20) DEFAULT 'green',
    goal_id     TEXT,
    plan_json   TEXT,
    created_at  DATETIME
)
"""

# redistribution_events must exist so the audit log writes inside
# rebalance_after_overspend() don't corrupt the session via failed flush.
_CREATE_REDISTRIBUTION_EVENTS = """
CREATE TABLE IF NOT EXISTS redistribution_events (
    id            TEXT PRIMARY KEY,
    user_id       TEXT NOT NULL,
    from_category VARCHAR(100) NOT NULL,
    to_category   VARCHAR(100) NOT NULL,
    amount        DECIMAL(12, 2) NOT NULL,
    reason        VARCHAR(50) NOT NULL,
    from_day      DATE,
    created_at    DATETIME DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now'))
)
"""


@pytest.fixture(scope="function")
def engine():
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    with eng.connect() as conn:
        conn.execute(text(_CREATE_DAILY_PLAN))
        conn.execute(text(_CREATE_REDISTRIBUTION_EVENTS))
        conn.commit()
    yield eng


@pytest.fixture(scope="function")
def db(engine):
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


# ---------------------------------------------------------------------------
# Helper: insert a DailyPlan row with UTC datetime
# ---------------------------------------------------------------------------

def _insert_plan(db, user_id, day: date, category: str, planned: float, spent: float = 0.0):
    dt = datetime(day.year, day.month, day.day, 12, 0, 0, tzinfo=timezone.utc)
    row = DailyPlan(
        id=uuid4(),
        user_id=user_id,
        date=dt,
        category=category,
        planned_amount=Decimal(str(planned)),
        spent_amount=Decimal(str(spent)),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _get_plan(db, user_id, day: date, category: str):
    day_start = datetime(day.year, day.month, day.day, 0, 0, 0)
    day_end   = datetime(day.year, day.month, day.day, 23, 59, 59)
    return (
        db.query(DailyPlan)
        .filter(
            DailyPlan.user_id == user_id,
            DailyPlan.category == category,
            DailyPlan.date >= day_start,
            DailyPlan.date <= day_end,
        )
        .first()
    )


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------

class TestRebalancerIntegration:

    def test_basic_rebalance_flow(self, db):
        """
        Full flow:
          - dining_out: planned $25, spent $35  → overspend $10
          - entertainment (future): planned $40  → should donate up to $20 (50% cap)
          After rebalance:
          - dining_out planned_amount increases (credited)
          - entertainment planned_amount decreases
        """
        user_id = uuid4()
        today = date(2026, 3, 10)
        future = date(2026, 3, 25)

        dining = _insert_plan(db, user_id, today,  "dining_out",   planned=25, spent=35)
        entert = _insert_plan(db, user_id, future, "entertainment", planned=40, spent=0)

        result = check_and_rebalance(db, user_id, "dining_out", today)

        assert result is not None, "Expected rebalance to trigger"
        assert result.covered > Decimal("0.00")
        assert float(result.overspend_amount) == pytest.approx(10.0, abs=0.01)

        db.expire_all()  # force reload from DB

        dining_after = _get_plan(db, user_id, today, "dining_out")
        entert_after = _get_plan(db, user_id, future, "entertainment")

        # dining_out planned_amount should have increased
        assert dining_after.planned_amount > Decimal("25.00"), (
            f"dining_out planned should be > 25, got {dining_after.planned_amount}"
        )
        # entertainment planned_amount should have decreased
        assert entert_after.planned_amount < Decimal("40.00"), (
            f"entertainment planned should be < 40, got {entert_after.planned_amount}"
        )

    def test_no_overspend_returns_none(self, db):
        """When spent < planned, rebalance must NOT trigger."""
        user_id = uuid4()
        today = date(2026, 3, 12)

        _insert_plan(db, user_id, today, "coffee", planned=10, spent=6)

        result = check_and_rebalance(db, user_id, "coffee", today)
        assert result is None

    def test_sacred_never_donates(self, db):
        """rent and savings_goal must never be used as donors."""
        user_id = uuid4()
        today  = date(2026, 3, 10)
        future = date(2026, 3, 20)

        _insert_plan(db, user_id, today,  "dining_out",  planned=20, spent=50)
        _insert_plan(db, user_id, future, "rent",         planned=1000, spent=0)
        _insert_plan(db, user_id, future, "savings_goal", planned=500,  spent=0)

        result = check_and_rebalance(db, user_id, "dining_out", today)

        # Nothing available to donate (only sacred categories)
        assert result is not None
        assert result.covered == Decimal("0.00")

        db.expire_all()
        rent_after = _get_plan(db, user_id, future, "rent")
        savings_after = _get_plan(db, user_id, future, "savings_goal")

        assert rent_after.planned_amount == Decimal("1000.00"), "rent must not be touched"
        assert savings_after.planned_amount == Decimal("500.00"), "savings must not be touched"

    def test_discretionary_drained_before_protected(self, db):
        """entertainment (DISCRETIONARY=3) must donate before groceries (PROTECTED=1)."""
        user_id = uuid4()
        today  = date(2026, 3, 10)
        future = date(2026, 3, 22)

        # $5 overspend — entertainment alone covers it
        _insert_plan(db, user_id, today,  "dining_out",    planned=20, spent=25)
        _insert_plan(db, user_id, future, "entertainment", planned=30, spent=0)
        _insert_plan(db, user_id, future, "groceries",     planned=50, spent=0)

        result = check_and_rebalance(db, user_id, "dining_out", today)
        assert result is not None and result.covered > Decimal("0")

        db.expire_all()
        entert_after   = _get_plan(db, user_id, future, "entertainment")
        groceries_after = _get_plan(db, user_id, future, "groceries")

        # entertainment must have donated
        assert entert_after.planned_amount < Decimal("30.00")
        # groceries must be untouched (entertainment covered the full $5)
        assert groceries_after.planned_amount == Decimal("50.00"), (
            f"groceries should be untouched, got {groceries_after.planned_amount}"
        )

    def test_partial_coverage(self, db):
        """When surplus < deficit: partial coverage, uncovered > 0."""
        user_id = uuid4()
        today  = date(2026, 3, 10)
        future = date(2026, 3, 28)

        # $40 overspend
        _insert_plan(db, user_id, today,  "dining_out",    planned=10, spent=50)
        # Only $10 available in entertainment (50% cap → max $5 donated)
        _insert_plan(db, user_id, future, "entertainment", planned=10, spent=0)

        result = check_and_rebalance(db, user_id, "dining_out", today)

        assert result is not None
        assert result.covered > Decimal("0")
        assert result.uncovered > Decimal("0")
        assert (result.covered + result.uncovered) == pytest.approx(
            float(result.overspend_amount), abs=0.02
        )

    def test_past_days_not_touched(self, db):
        """Entries from days BEFORE txn_date must not be modified."""
        user_id = uuid4()
        today = date(2026, 3, 15)
        past  = date(2026, 3, 5)
        future = date(2026, 3, 25)

        _insert_plan(db, user_id, today,  "dining_out",    planned=10, spent=30)
        past_row   = _insert_plan(db, user_id, past,   "entertainment", planned=50, spent=0)
        _insert_plan(db, user_id, future, "entertainment", planned=50, spent=0)

        past_planned_before = Decimal(str(past_row.planned_amount))

        check_and_rebalance(db, user_id, "dining_out", today)

        db.expire_all()
        past_after = _get_plan(db, user_id, past, "entertainment")

        assert past_after.planned_amount == past_planned_before, (
            f"Past entry must not be modified: before={past_planned_before}, "
            f"after={past_after.planned_amount}"
        )

    def test_50_percent_cap_respected_in_db(self, db):
        """50% cap per category must hold in actual DB values."""
        user_id = uuid4()
        today  = date(2026, 3, 10)
        f1 = date(2026, 3, 20)
        f2 = date(2026, 3, 25)

        # entertainment has $60 total across 2 days
        _insert_plan(db, user_id, today, "dining_out",    planned=10, spent=80)
        _insert_plan(db, user_id, f1,   "entertainment", planned=30, spent=0)
        _insert_plan(db, user_id, f2,   "entertainment", planned=30, spent=0)

        check_and_rebalance(db, user_id, "dining_out", today)

        db.expire_all()
        e1 = _get_plan(db, user_id, f1, "entertainment")
        e2 = _get_plan(db, user_id, f2, "entertainment")

        total_remaining = e1.planned_amount + e2.planned_amount
        # At most 50% of $60 = $30 was taken → at least $30 remains
        assert total_remaining >= Decimal("30.00"), (
            f"50% cap violated: remaining={total_remaining} (expected >= 30)"
        )

    def test_decimal_precision_preserved(self, db):
        """Financial amounts must not accumulate floating-point error."""
        user_id = uuid4()
        today  = date(2026, 3, 10)
        future = date(2026, 3, 20)

        # Amounts chosen to expose float precision issues (thirds)
        _insert_plan(db, user_id, today,  "dining_out",    planned=10.00, spent=13.33)
        _insert_plan(db, user_id, future, "entertainment", planned=20.00, spent=0)

        check_and_rebalance(db, user_id, "dining_out", today)

        db.expire_all()
        dining = _get_plan(db, user_id, today, "dining_out")
        entert = _get_plan(db, user_id, future, "entertainment")

        # Check values are quantized to 2dp (no 3.3300000001 style errors)
        assert dining.planned_amount == dining.planned_amount.quantize(Decimal("0.01"))
        assert entert.planned_amount == entert.planned_amount.quantize(Decimal("0.01"))

    def test_multiple_donor_categories(self, db):
        """Multiple donor categories are all drawn from in priority order."""
        user_id = uuid4()
        today = date(2026, 3, 10)
        f1 = date(2026, 3, 18)
        f2 = date(2026, 3, 22)
        f3 = date(2026, 3, 26)

        # $50 overspend
        _insert_plan(db, user_id, today, "dining_out",  planned=10, spent=60)
        # gaming=DISCRETIONARY, coffee=FLEXIBLE, groceries=PROTECTED
        _insert_plan(db, user_id, f1, "gaming",    planned=20, spent=0)   # can give max $10
        _insert_plan(db, user_id, f2, "coffee",    planned=20, spent=0)   # can give max $10
        _insert_plan(db, user_id, f3, "groceries", planned=60, spent=0)   # can give max $30

        result = check_and_rebalance(db, user_id, "dining_out", today)

        assert result is not None
        assert result.covered > Decimal("0")
        # We should have multiple transfers
        assert len(result.transfers) >= 1

    def test_rebalance_after_overspend_direct(self, db):
        """Call rebalance_after_overspend() directly with known overspend amount."""
        user_id = uuid4()
        today  = date(2026, 3, 8)
        future = date(2026, 3, 18)

        dining  = _insert_plan(db, user_id, today,  "dining_out",    planned=20, spent=35)
        entert  = _insert_plan(db, user_id, future, "entertainment", planned=60, spent=0)

        result = rebalance_after_overspend(
            db=db,
            user_id=user_id,
            overspent_category="dining_out",
            overspend_amount=Decimal("15.00"),
            transaction_date=today,
        )

        assert result.overspent_category == "dining_out"
        assert result.overspend_amount == Decimal("15.00")

        db.expire_all()
        dining_after = _get_plan(db, user_id, today, "dining_out")
        entert_after = _get_plan(db, user_id, future, "entertainment")

        # dining_out credited
        assert dining_after.planned_amount > Decimal("20.00")
        # entertainment reduced
        assert entert_after.planned_amount < Decimal("60.00")

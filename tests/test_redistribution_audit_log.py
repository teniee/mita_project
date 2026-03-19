"""
Tests for DB-backed redistribution audit log (Problem 2 fix).

Verifies that:
- Events are written to redistribution_events table, not memory
- Events survive a "restart" (fresh session reads them back)
- get_redistribution_history() returns correct data ordered newest-first
- clear_user_audit_log() deletes only the target user's rows
- from_day accepts str / date / datetime / None
- amount stored as Decimal, returned as float
- limit parameter is respected
- Different users see only their own events
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

from app.services.redistribution_audit_log import (
    clear_user_audit_log,
    get_redistribution_history,
    record_redistribution_event,
)

# ---------------------------------------------------------------------------
# SQLite fixtures — redistribution_events table only
# ---------------------------------------------------------------------------

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS redistribution_events (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL,
    from_category VARCHAR(100) NOT NULL,
    to_category   VARCHAR(100) NOT NULL,
    amount        DECIMAL(12, 2) NOT NULL,
    reason        VARCHAR(50) NOT NULL,
    from_day      DATE,
    created_at    DATETIME DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now'))
)
"""

# Also need users table for FK — skip FK in SQLite (not enforced by default)


@pytest.fixture(scope="function")
def engine():
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    with eng.connect() as conn:
        conn.execute(text(_CREATE_TABLE))
        conn.commit()
    yield eng


@pytest.fixture(scope="function")
def db(engine):
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


@pytest.fixture(scope="function")
def fresh_db(engine):
    """Second session — simulates a server restart reading from same DB."""
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestRecordRedistributionEvent:

    def test_event_written_to_db(self, db):
        """record_redistribution_event must INSERT to DB, not memory."""
        user_id = uuid4()
        record_redistribution_event(
            db=db,
            user_id=user_id,
            from_category="entertainment",
            to_category="dining_out",
            amount=Decimal("15.00"),
            reason="realtime_rebalance",
        )
        db.commit()

        history = get_redistribution_history(db=db, user_id=user_id)
        assert len(history) == 1
        assert history[0]["from_category"] == "entertainment"
        assert history[0]["to_category"] == "dining_out"
        assert history[0]["amount"] == 15.0
        assert history[0]["reason"] == "realtime_rebalance"

    def test_event_survives_session_restart(self, db, fresh_db):
        """Data written in one session must be readable in a new session."""
        user_id = uuid4()
        record_redistribution_event(
            db=db,
            user_id=user_id,
            from_category="gaming",
            to_category="groceries",
            amount=Decimal("8.50"),
            reason="budget_redistribution",
        )
        db.commit()

        # fresh_db = new session, simulating server restart
        history = get_redistribution_history(db=fresh_db, user_id=user_id)
        assert len(history) == 1
        assert history[0]["from_category"] == "gaming"
        assert history[0]["amount"] == 8.5

    def test_returns_event_dict(self, db):
        """return value must be a dict with expected keys."""
        user_id = uuid4()
        result = record_redistribution_event(
            db=db,
            user_id=user_id,
            from_category="hobbies",
            to_category="coffee",
            amount=Decimal("5.00"),
            reason="realtime_rebalance",
        )
        db.commit()

        assert isinstance(result, dict)
        assert "id" in result
        assert result["from_category"] == "hobbies"
        assert result["to_category"] == "coffee"
        assert result["amount"] == 5.0

    def test_from_day_as_date_object(self, db):
        user_id = uuid4()
        d = date(2026, 3, 15)
        record_redistribution_event(
            db=db,
            user_id=user_id,
            from_category="entertainment",
            to_category="dining_out",
            amount=Decimal("10.00"),
            reason="realtime_rebalance",
            from_day=d,
        )
        db.commit()

        history = get_redistribution_history(db=db, user_id=user_id)
        assert history[0]["from_day"] == "2026-03-15"

    def test_from_day_as_datetime_object(self, db):
        user_id = uuid4()
        dt = datetime(2026, 3, 20, 14, 30, 0, tzinfo=timezone.utc)
        record_redistribution_event(
            db=db,
            user_id=user_id,
            from_category="gaming",
            to_category="dining_out",
            amount=Decimal("7.00"),
            reason="realtime_rebalance",
            from_day=dt,
        )
        db.commit()

        history = get_redistribution_history(db=db, user_id=user_id)
        assert history[0]["from_day"] == "2026-03-20"

    def test_from_day_as_isoformat_string(self, db):
        user_id = uuid4()
        record_redistribution_event(
            db=db,
            user_id=user_id,
            from_category="clothing",
            to_category="dining_out",
            amount=Decimal("3.00"),
            reason="budget_redistribution",
            from_day="2026-03-10",
        )
        db.commit()

        history = get_redistribution_history(db=db, user_id=user_id)
        assert history[0]["from_day"] == "2026-03-10"

    def test_from_day_as_datetime_string(self, db):
        user_id = uuid4()
        record_redistribution_event(
            db=db,
            user_id=user_id,
            from_category="delivery",
            to_category="dining_out",
            amount=Decimal("4.00"),
            reason="realtime_rebalance",
            from_day="2026-03-12T09:00:00",
        )
        db.commit()

        history = get_redistribution_history(db=db, user_id=user_id)
        assert history[0]["from_day"] == "2026-03-12"

    def test_from_day_none(self, db):
        user_id = uuid4()
        record_redistribution_event(
            db=db,
            user_id=user_id,
            from_category="entertainment",
            to_category="dining_out",
            amount=Decimal("6.00"),
            reason="realtime_rebalance",
            from_day=None,
        )
        db.commit()

        history = get_redistribution_history(db=db, user_id=user_id)
        assert history[0]["from_day"] is None

    def test_amount_precision(self, db):
        """Decimal amounts must be stored and returned with correct precision."""
        user_id = uuid4()
        record_redistribution_event(
            db=db,
            user_id=user_id,
            from_category="coffee",
            to_category="dining_out",
            amount=Decimal("12.34"),
            reason="realtime_rebalance",
        )
        db.commit()

        history = get_redistribution_history(db=db, user_id=user_id)
        assert history[0]["amount"] == pytest.approx(12.34, abs=0.001)

    def test_multiple_events_ordered_newest_first(self, db):
        """History must be ordered newest → oldest."""
        import time
        user_id = uuid4()

        for category in ["entertainment", "gaming", "hobbies"]:
            record_redistribution_event(
                db=db,
                user_id=user_id,
                from_category=category,
                to_category="dining_out",
                amount=Decimal("1.00"),
                reason="realtime_rebalance",
            )
            db.commit()
            time.sleep(0.01)  # ensure distinct created_at

        history = get_redistribution_history(db=db, user_id=user_id)
        assert len(history) == 3
        # newest first
        assert history[0]["from_category"] == "hobbies"
        assert history[1]["from_category"] == "gaming"
        assert history[2]["from_category"] == "entertainment"


class TestGetRedistributionHistory:

    def test_empty_history(self, db):
        """New user has no history."""
        user_id = uuid4()
        history = get_redistribution_history(db=db, user_id=user_id)
        assert history == []

    def test_limit_respected(self, db):
        """limit parameter must cap the number of returned events."""
        user_id = uuid4()
        for i in range(10):
            record_redistribution_event(
                db=db,
                user_id=user_id,
                from_category="entertainment",
                to_category="dining_out",
                amount=Decimal(str(i + 1)),
                reason="realtime_rebalance",
            )
        db.commit()

        history = get_redistribution_history(db=db, user_id=user_id, limit=3)
        assert len(history) == 3

    def test_user_isolation(self, db):
        """Users must see only their own events."""
        user_a = uuid4()
        user_b = uuid4()

        record_redistribution_event(
            db=db, user_id=user_a,
            from_category="gaming", to_category="dining_out",
            amount=Decimal("10.00"), reason="realtime_rebalance",
        )
        record_redistribution_event(
            db=db, user_id=user_b,
            from_category="clothing", to_category="groceries",
            amount=Decimal("5.00"), reason="budget_redistribution",
        )
        db.commit()

        history_a = get_redistribution_history(db=db, user_id=user_a)
        history_b = get_redistribution_history(db=db, user_id=user_b)

        assert len(history_a) == 1
        assert history_a[0]["from_category"] == "gaming"

        assert len(history_b) == 1
        assert history_b[0]["from_category"] == "clothing"

    def test_history_dict_has_required_keys(self, db):
        """Each history entry must have all expected keys."""
        user_id = uuid4()
        record_redistribution_event(
            db=db, user_id=user_id,
            from_category="entertainment", to_category="dining_out",
            amount=Decimal("9.99"), reason="realtime_rebalance",
            from_day=date(2026, 3, 15),
        )
        db.commit()

        history = get_redistribution_history(db=db, user_id=user_id)
        entry = history[0]

        required_keys = {"id", "timestamp", "from_category", "to_category",
                         "amount", "reason", "from_day"}
        assert required_keys.issubset(entry.keys()), (
            f"Missing keys: {required_keys - entry.keys()}"
        )


class TestClearUserAuditLog:

    def test_clears_only_target_user(self, db):
        """clear_user_audit_log must delete only the specified user's events."""
        user_a = uuid4()
        user_b = uuid4()

        for uid in (user_a, user_b):
            record_redistribution_event(
                db=db, user_id=uid,
                from_category="entertainment", to_category="dining_out",
                amount=Decimal("5.00"), reason="realtime_rebalance",
            )
        db.commit()

        deleted = clear_user_audit_log(db=db, user_id=user_a)
        assert deleted == 1

        assert get_redistribution_history(db=db, user_id=user_a) == []
        assert len(get_redistribution_history(db=db, user_id=user_b)) == 1

    def test_clear_nonexistent_user_returns_zero(self, db):
        """Clearing a user with no events returns 0."""
        result = clear_user_audit_log(db=db, user_id=uuid4())
        assert result == 0

    def test_clear_removes_all_events_for_user(self, db):
        """All events for the user are removed, not just the first."""
        user_id = uuid4()
        for i in range(5):
            record_redistribution_event(
                db=db, user_id=user_id,
                from_category="gaming", to_category="dining_out",
                amount=Decimal(str(i + 1)), reason="realtime_rebalance",
            )
        db.commit()

        deleted = clear_user_audit_log(db=db, user_id=user_id)
        assert deleted == 5
        assert get_redistribution_history(db=db, user_id=user_id) == []

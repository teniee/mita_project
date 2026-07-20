"""Regression tests: daily-plan bucketing follows the USER's calendar day.

Bug context (session-6 on-device journey, 2026-07-19):
- A transaction picked as "June 30" at 02:00 Europe/Sofia was stored with the
  correct UTC instant (2026-06-29T23:00Z) but bucketed into the 2026-06-29
  DailyPlan row — `apply_transaction_to_plan`/`recalculate_plan_spent` and the
  transaction services derived the day with `.date()` on the UTC value.
- `/api/budget/live_status` reported "today" as the UTC date, so every daily
  figure was off by one day between local midnight and UTC midnight.

Invariant under test: the DailyPlan day key for a transaction is the calendar
day the user experienced in their own timezone; create, edit (day move), and
delete all agree on that key; a UTC-timezone user keeps the old behavior.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.db.models import DailyPlan, Transaction, User
from app.services.core.engine.expense_tracker import (
    apply_transaction_to_plan,
    local_day_of,
    local_day_utc_window,
    recalculate_plan_spent,
)

SOFIA = "Europe/Sofia"
# 2026-06-29T23:00:33Z == 2026-06-30 02:00:33 in Europe/Sofia (UTC+3, EEST).
# Stored UTC-aware exactly as production does (add_transaction always converts
# spent_at to UTC via from_user_timezone); a naive value would be misread as
# the DB session's local zone.
NEAR_MIDNIGHT_UTC = datetime(2026, 6, 29, 23, 0, 33, tzinfo=timezone.utc)


@pytest.fixture
def db_session():
    import app.core.session as session_module

    gen = session_module.get_db()
    db = next(gen)
    try:
        yield db
    finally:
        gen.close()


def _make_user(db, tz):
    user = User(
        id=uuid4(),
        email=f"tzbucket_{uuid4().hex[:8]}@mita.app",
        password_hash="hashed_password_123",
        has_onboarded=True,
        monthly_income=Decimal("5000.00"),
        timezone=tz,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _plan_days(db, user_id, category):
    rows = (
        db.query(DailyPlan)
        .filter(DailyPlan.user_id == user_id, DailyPlan.category == category)
        .all()
    )
    return {
        (r.date.date() if hasattr(r.date, "date") else r.date): Decimal(
            r.spent_amount or 0
        )
        for r in rows
    }


def test_local_day_of_crosses_utc_midnight():
    assert local_day_of(NEAR_MIDNIGHT_UTC, SOFIA) == date(2026, 6, 30)
    assert local_day_of(NEAR_MIDNIGHT_UTC, "UTC") == date(2026, 6, 29)


def test_local_day_utc_window_sofia():
    start, end = local_day_utc_window(date(2026, 6, 30), SOFIA)
    # Window is returned as naive-UTC (matches how spent_at is compared).
    assert start == datetime(2026, 6, 29, 21, 0, 0)
    assert end == datetime(2026, 6, 30, 21, 0, 0)
    naive_near_midnight = NEAR_MIDNIGHT_UTC.replace(tzinfo=None)
    assert start <= naive_near_midnight < end


def test_invalid_timezone_falls_back_to_utc():
    assert local_day_of(NEAR_MIDNIGHT_UTC, "Not/AZone") == date(2026, 6, 29)
    assert local_day_of(NEAR_MIDNIGHT_UTC, None) == date(2026, 6, 29)


def test_first_of_month_local_bucket():
    # 2026-07-31T21:30Z == 2026-08-01 00:30 Sofia (EEST, UTC+3): the spend
    # belongs to August 1 locally even though the UTC date is July 31.
    instant = datetime(2026, 7, 31, 21, 30, 0, tzinfo=timezone.utc)
    assert local_day_of(instant, SOFIA) == date(2026, 8, 1)
    assert local_day_of(instant, "UTC") == date(2026, 7, 31)


def test_dst_offset_changes_local_day():
    # Same 21:30 UTC wall time buckets to different LOCAL days across the DST
    # boundary: winter Sofia is UTC+2 (still same day), summer is UTC+3 (next
    # day). Proves the offset is zone-aware, not a fixed shift.
    winter = datetime(2026, 1, 15, 21, 30, 0, tzinfo=timezone.utc)
    summer = datetime(2026, 7, 15, 21, 30, 0, tzinfo=timezone.utc)
    assert local_day_of(winter, SOFIA) == date(2026, 1, 15)  # +2h -> 23:30
    assert local_day_of(summer, SOFIA) == date(2026, 7, 16)  # +3h -> 00:30


def test_dst_window_offsets():
    # The UTC window for a local day widens/narrows with the seasonal offset.
    w_start, w_end = local_day_utc_window(date(2026, 1, 15), SOFIA)
    assert w_start == datetime(2026, 1, 14, 22, 0, 0)  # UTC+2
    s_start, s_end = local_day_utc_window(date(2026, 7, 15), SOFIA)
    assert s_start == datetime(2026, 7, 14, 21, 0, 0)  # UTC+3


def test_apply_buckets_near_midnight_txn_to_local_day(db_session):
    user = _make_user(db_session, SOFIA)
    txn = Transaction(
        user_id=user.id,
        category="groceries",
        amount=Decimal("100.00"),
        currency="USD",
        spent_at=NEAR_MIDNIGHT_UTC,
    )
    db_session.add(txn)
    db_session.commit()
    db_session.refresh(txn)

    apply_transaction_to_plan(db_session, txn)

    days = _plan_days(db_session, user.id, "groceries")
    assert days.get(date(2026, 6, 30)) == Decimal("100.00"), days
    assert date(2026, 6, 29) not in days or days[date(2026, 6, 29)] == 0


def test_recalculate_sums_local_day_window(db_session):
    user = _make_user(db_session, SOFIA)
    # Two txns on Sofia's June 30: one just after local midnight (UTC June 29)
    # and one at local noon (UTC June 30). Both must land in the same bucket.
    for spent_at in (
        NEAR_MIDNIGHT_UTC,
        datetime(2026, 6, 30, 9, 0, 0, tzinfo=timezone.utc),
    ):
        db_session.add(
            Transaction(
                user_id=user.id,
                category="groceries",
                amount=Decimal("40.00"),
                currency="USD",
                spent_at=spent_at,
            )
        )
    db_session.commit()

    recalculate_plan_spent(
        db_session, user.id, date(2026, 6, 30), "groceries", tz=SOFIA
    )

    days = _plan_days(db_session, user.id, "groceries")
    assert days.get(date(2026, 6, 30)) == Decimal("80.00"), days


def test_delete_reverses_local_day_bucket(db_session):
    user = _make_user(db_session, SOFIA)
    txn = Transaction(
        user_id=user.id,
        category="groceries",
        amount=Decimal("100.00"),
        currency="USD",
        spent_at=NEAR_MIDNIGHT_UTC,
    )
    db_session.add(txn)
    db_session.commit()
    db_session.refresh(txn)
    apply_transaction_to_plan(db_session, txn)

    from app.api.transactions.services import delete_transaction

    assert delete_transaction(user, txn.id, db_session) is True

    days = _plan_days(db_session, user.id, "groceries")
    assert days.get(date(2026, 6, 30), Decimal("0")) == Decimal("0"), days


def test_utc_user_keeps_utc_day(db_session):
    user = _make_user(db_session, "UTC")
    txn = Transaction(
        user_id=user.id,
        category="groceries",
        amount=Decimal("55.00"),
        currency="USD",
        spent_at=NEAR_MIDNIGHT_UTC,
    )
    db_session.add(txn)
    db_session.commit()
    db_session.refresh(txn)

    apply_transaction_to_plan(db_session, txn)

    days = _plan_days(db_session, user.id, "groceries")
    assert days.get(date(2026, 6, 29)) == Decimal("55.00"), days

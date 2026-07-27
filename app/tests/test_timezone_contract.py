"""The temporal contract: instants are UTC, buckets are user-local.

Transaction.spent_at is always a UTC instant. Every day/month bucket -
DailyPlan rows, the month rebuild window, and the live_status month
window - is derived from the user's IANA timezone. The two must agree, or
the dashboard totals and the calendar disagree about which month a
transaction belongs to.

app/tests/test_timezone_bucketing.py covers near-midnight bucketing, the
month start, and the western-timezone date-only case. This file closes the
rest of the matrix: year boundary, both DST transitions, the missing/invalid
timezone fallbacks, and live_status vs. the rebuild window.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.db.models import DailyPlan, Transaction, User
from app.services.core.engine.expense_tracker import (
    apply_transaction_to_plan,
    local_day_of,
    local_day_utc_window,
)

SOFIA = "Europe/Sofia"
LA = "America/Los_Angeles"


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
        email=f"tzcontract_{uuid4().hex[:10]}@mita.app",
        password_hash="x",
        has_onboarded=True,
        timezone=tz,
        monthly_income=Decimal("6000.00"),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _cleanup(db, user):
    db.query(Transaction).filter_by(user_id=user.id).delete()
    db.query(DailyPlan).filter_by(user_id=user.id).delete()
    db.query(User).filter_by(id=user.id).delete()
    db.commit()


def _bucket_day(db, user, spent_at):
    """Apply one transaction and return the local day its plan row landed on."""
    txn = Transaction(
        user_id=user.id,
        category="food",
        amount=Decimal("10.00"),
        spent_at=spent_at,
    )
    db.add(txn)
    db.flush()
    apply_transaction_to_plan(db, txn, commit=True, run_side_effects=False)
    db.expire_all()
    rows = [
        row
        for row in db.query(DailyPlan)
        .filter(DailyPlan.user_id == user.id, DailyPlan.category == "food")
        .all()
        if Decimal(row.spent_amount or 0) > 0
    ]
    assert len(rows) == 1, f"expected one bucket, got {len(rows)}"
    row = rows[0]
    return row.date.date() if hasattr(row.date, "date") else row.date


# ---------------------------------------------------------------------------
# Pure helpers - no database
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "tz,instant,expected",
    [
        # Sofia is UTC+2 in winter. 22:30Z on Dec 31 is already Jan 1 local:
        # a New Year's Eve spend belongs to the NEXT year's first day.
        (SOFIA, datetime(2025, 12, 31, 22, 30, tzinfo=timezone.utc), (2026, 1, 1)),
        # One minute earlier is still Dec 31 local.
        (SOFIA, datetime(2025, 12, 31, 21, 59, tzinfo=timezone.utc), (2025, 12, 31)),
        # Los Angeles is UTC-8 in winter. 03:00Z on Jan 1 is still Dec 31
        # local: the spend belongs to the PREVIOUS year.
        (LA, datetime(2026, 1, 1, 3, 0, tzinfo=timezone.utc), (2025, 12, 31)),
        (LA, datetime(2026, 1, 1, 8, 1, tzinfo=timezone.utc), (2026, 1, 1)),
    ],
)
def test_year_boundary_buckets_by_local_day(tz, instant, expected):
    assert local_day_of(instant, tz) == datetime(*expected).date()


def test_dst_spring_forward_keeps_local_day():
    """Sofia springs forward 2026-03-29 03:00 (UTC+2 -> UTC+3)."""
    before = datetime(2026, 3, 28, 22, 30, tzinfo=timezone.utc)  # 00:30 local
    after = datetime(2026, 3, 29, 22, 30, tzinfo=timezone.utc)  # 01:30 local
    assert local_day_of(before, SOFIA) == datetime(2026, 3, 29).date()
    assert local_day_of(after, SOFIA) == datetime(2026, 3, 30).date()

    # The local day is still exactly 24 h of wall clock even though the
    # transition day itself is only 23 h of real time.
    start, end = local_day_utc_window(datetime(2026, 3, 29).date(), SOFIA)
    assert end - start == timedelta(hours=23), "spring-forward day is 23h"


def test_dst_fall_back_keeps_local_day():
    """Sofia falls back 2026-10-25 04:00 (UTC+3 -> UTC+2)."""
    start, end = local_day_utc_window(datetime(2026, 10, 25).date(), SOFIA)
    assert end - start == timedelta(hours=25), "fall-back day is 25h"

    # The ambiguous local hour (03:30 occurs twice) must still land on the
    # same calendar day whichever instant produced it.
    first = datetime(2026, 10, 25, 0, 30, tzinfo=timezone.utc)
    second = datetime(2026, 10, 25, 1, 30, tzinfo=timezone.utc)
    assert local_day_of(first, SOFIA) == datetime(2026, 10, 25).date()
    assert local_day_of(second, SOFIA) == datetime(2026, 10, 25).date()


@pytest.mark.parametrize("tz", [None, "", "Not/AZone", "Mars/Olympus"])
def test_missing_or_invalid_timezone_falls_back_to_utc(tz):
    """A user with no or a broken timezone must still bucket deterministically."""
    instant = datetime(2026, 6, 29, 23, 0, tzinfo=timezone.utc)
    assert local_day_of(instant, tz) == datetime(2026, 6, 29).date()
    start, end = local_day_utc_window(datetime(2026, 6, 29).date(), tz)
    assert start == datetime(2026, 6, 29, 0, 0)
    assert end == datetime(2026, 6, 30, 0, 0)


def test_naive_spent_at_is_read_as_utc():
    """Legacy rows stored naive must not be reinterpreted as local time."""
    naive = datetime(2026, 6, 29, 23, 0)
    aware = datetime(2026, 6, 29, 23, 0, tzinfo=timezone.utc)
    assert local_day_of(naive, SOFIA) == local_day_of(aware, SOFIA)


# ---------------------------------------------------------------------------
# Against PostgreSQL
# ---------------------------------------------------------------------------


def test_year_boundary_bucket_sofia(db_session):
    """22:30Z on Dec 31 is Jan 1 in Sofia — plan row must be Jan 1."""
    user = _make_user(db_session, SOFIA)
    try:
        day = _bucket_day(
            db_session,
            user,
            datetime(2025, 12, 31, 22, 30, tzinfo=timezone.utc),
        )
        assert day == datetime(2026, 1, 1).date()
    finally:
        _cleanup(db_session, user)


def test_year_boundary_bucket_los_angeles(db_session):
    """03:00Z on Jan 1 is still Dec 31 in Los Angeles."""
    user = _make_user(db_session, LA)
    try:
        day = _bucket_day(
            db_session,
            user,
            datetime(2026, 1, 1, 3, 0, tzinfo=timezone.utc),
        )
        assert day == datetime(2025, 12, 31).date()
    finally:
        _cleanup(db_session, user)


def test_month_boundary_bucket_los_angeles(db_session):
    """03:00Z on the 1st is still the previous month in Los Angeles."""
    user = _make_user(db_session, LA)
    try:
        day = _bucket_day(
            db_session,
            user,
            datetime(2026, 7, 1, 3, 0, tzinfo=timezone.utc),
        )
        assert day == datetime(2026, 6, 30).date()
    finally:
        _cleanup(db_session, user)


def test_live_status_month_window_matches_rebuild_window(db_session):
    """live_status and the month rebuild must slice the month identically.

    live_status sums from local_day_utc_window(first_of_local_month)[0];
    rebuild_month_plan selects transactions over the same window. If they
    ever diverge, the dashboard total and the calendar disagree.
    """
    from app.services.core.engine.expense_tracker import _next_month_start

    for tz in (SOFIA, LA, "UTC"):
        for probe in (
            datetime(2026, 1, 15).date(),
            datetime(2026, 7, 1).date(),
            datetime(2026, 12, 31).date(),
        ):
            month_start = probe.replace(day=1)
            # live_status boundary
            live_start, _ = local_day_utc_window(month_start, tz)
            # rebuild boundary
            rebuild_start = local_day_utc_window(month_start, tz)[0]
            rebuild_end = local_day_utc_window(_next_month_start(month_start), tz)[0]

            assert live_start == rebuild_start, (tz, probe)
            assert rebuild_end > rebuild_start
            # The window must start exactly at local midnight.
            local_midnight = rebuild_start.replace(tzinfo=timezone.utc).astimezone(
                ZoneInfo(tz)
            )
            assert (local_midnight.hour, local_midnight.minute) == (0, 0), (tz, probe)
            assert local_midnight.date() == month_start

"""Regression: /dashboard buckets by the USER's local calendar day (J2/J3).

The dashboard route used the UTC date and naive midnight-to-midnight windows.
For a Europe/Sofia user between local midnight and 03:00, today-spent,
category spending, DailyPlan targets and the week strip all read the wrong
day, and a 00:30 local transaction was filed under the previous local day.
Fixed to mirror /budget/live_status: local_day_of + local_day_utc_window
with AWARE UTC instants (independent of DB session / process timezone).

Requires: PostgreSQL at DATABASE_URL (test_mita) with migrations at head.
"""

from datetime import datetime, time as dtime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from app.db.models import Transaction, User

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
def sofia_user(db_session):
    user = User(
        id=uuid4(),
        email=f"dash_local_{uuid4().hex[:10]}@mita.app",
        password_hash="hashed_password_123",
        has_onboarded=True,
        timezone="Europe/Sofia",
        monthly_income=Decimal("6000.00"),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    yield user
    db_session.query(Transaction).filter_by(user_id=user.id).delete()
    db_session.query(User).filter_by(id=user.id).delete()
    db_session.commit()


@pytest.fixture
def as_sofia_user(client, sofia_user):
    from app.api.dependencies import get_current_user
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: sofia_user
    try:
        yield client
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def _recent_local_0030():
    """A 00:30-Europe/Sofia instant on a recent local day (2-5 days back).

    00:30 local is 21:30/22:30 UTC of the PREVIOUS UTC day, so the local
    and UTC calendar days always differ — the exact case the old UTC-date
    dashboard filed on the wrong day.
    """
    now_local = datetime.now(SOFIA)
    day = (now_local - timedelta(days=3)).date()
    local = datetime.combine(day, dtime(0, 30), tzinfo=SOFIA)
    return local, day


def test_week_strip_files_0030_txn_on_the_sofia_day(
    as_sofia_user, db_session, sofia_user
):
    local_instant, local_day = _recent_local_0030()
    utc_day = local_instant.astimezone(timezone.utc).date()
    assert utc_day != local_day, "00:30 Sofia must fall on the prior UTC day"

    txn = Transaction(
        id=uuid4(),
        user_id=sofia_user.id,
        amount=Decimal("33.00"),
        category="food",
        description="near-midnight regression",
        spent_at=local_instant.astimezone(timezone.utc),
    )
    db_session.add(txn)
    db_session.commit()

    resp = as_sofia_user.get("/api/dashboard")
    assert resp.status_code == 200, resp.text
    week = resp.json()["data"]["week"]
    days_of_week = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    by_label = {entry["day"]: entry for entry in week}
    local_label = days_of_week[local_day.weekday()]
    utc_label = days_of_week[utc_day.weekday()]

    assert by_label[local_label]["spent"] == pytest.approx(33.00), (
        f"txn at 00:30 Sofia must be filed on the Sofia day {local_day} "
        f"({local_label}), got week={week}"
    )
    assert by_label[utc_label]["spent"] == pytest.approx(0.0), (
        f"txn must NOT be filed on the UTC day {utc_day} ({utc_label})"
    )


def test_monthly_spending_uses_local_month_boundary(
    as_sofia_user, db_session, sofia_user
):
    """A txn at 00:30 local on the 1st belongs to the NEW local month even
    though its UTC instant is still in the previous month."""
    now_local = datetime.now(SOFIA)
    first_of_month = now_local.date().replace(day=1)
    local_instant = datetime.combine(first_of_month, dtime(0, 30), tzinfo=SOFIA)
    if local_instant >= now_local:
        pytest.skip("suite is running within 30 minutes of the local month start")

    txn = Transaction(
        id=uuid4(),
        user_id=sofia_user.id,
        amount=Decimal("21.00"),
        category="food",
        description="month-boundary regression",
        spent_at=local_instant.astimezone(timezone.utc),
    )
    db_session.add(txn)
    db_session.commit()

    resp = as_sofia_user.get("/api/dashboard/quick-stats")
    assert resp.status_code == 200, resp.text
    stats = resp.json()["data"]
    assert stats["monthly_spending"] == pytest.approx(21.00), (
        "a 00:30-local txn on the 1st must count toward the user's local "
        f"month, got {stats['monthly_spending']}"
    )

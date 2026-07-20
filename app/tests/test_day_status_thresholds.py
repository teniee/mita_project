"""Unit coverage for update_day_status thresholds (green/yellow/red).

The Phase-2 device matrix demonstrated green and red live; the yellow
window is actively suppressed in production by the auto-rebalancer
(redistribution covers small overspends), so its boundary is pinned here
deterministically: delta <= 0 green, 0 < delta <= max($2, min($25, 5%))
yellow, beyond red.
"""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from app.db.models import DailyPlan, User
from app.services.core.engine.calendar_updater import update_day_status

DAY = date(2026, 7, 15)


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
        email=f"day_status_{uuid4().hex[:10]}@mita.app",
        password_hash="x",
        timezone="UTC",
        monthly_income=Decimal("3000.00"),
    )
    db_session.add(u)
    db_session.commit()
    yield u
    db_session.query(DailyPlan).filter_by(user_id=u.id).delete()
    db_session.query(User).filter_by(id=u.id).delete()
    db_session.commit()


def _seed(db, user, planned, spent):
    db.query(DailyPlan).filter_by(user_id=user.id).delete()
    db.add(
        DailyPlan(
            user_id=user.id,
            date=DAY,
            category="groceries",
            planned_amount=Decimal(planned),
            daily_budget=Decimal(planned),
            spent_amount=Decimal(spent),
        )
    )
    db.commit()


@pytest.mark.parametrize(
    "planned,spent,expected",
    [
        ("100.00", "50.00", "green"),   # under budget
        ("100.00", "100.00", "green"),  # exactly on budget
        ("100.00", "101.00", "yellow"), # over by $1 <= 5% threshold
        ("100.00", "104.99", "yellow"), # over by $4.99 <= $5 threshold
        ("100.00", "105.01", "red"),    # over beyond the 5% threshold
        ("20.00", "21.50", "yellow"),   # small budget: floor is $2, over $1.50
        ("20.00", "22.50", "red"),      # small budget: over $2.50 > $2 floor
        ("1000.00", "1024.00", "yellow"),  # big budget: cap $25, over $24
        ("1000.00", "1026.00", "red"),  # big budget: over $26 > $25 cap
    ],
)
def test_day_status_thresholds(db_session, user, planned, spent, expected):
    _seed(db_session, user, planned, spent)
    result = update_day_status(db_session, user.id, DAY)
    assert result["status"] == expected, result
    row = db_session.query(DailyPlan).filter_by(user_id=user.id).one()
    assert row.status == expected

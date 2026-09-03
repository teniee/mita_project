"""Regression: the affordability check must find the budget the planner wrote.

`build_monthly_budget` writes plan-vocabulary buckets into `daily_plan`
("groceries", "dining out", "coffee", "transport public", ...), while the app
posts API-vocabulary categories ("food", "transportation", ...). The lookup
used an exact `category ==` match, so it missed for *every* category the app
can send: a freshly-onboarded user whose dashboard showed "Groceries $13.71 /
Coffee $5.40 / Transport public $30.00" for today was told, on saving a $20
food expense, "No budget set for 'food'" — with an unactionable suggestion to
set one "in settings". Device-reproduced during the pre-launch frontend pass.

Requires: PostgreSQL at DATABASE_URL with migrations at head.
"""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.config.category_aliases import matches_category, plan_categories_for
from app.db.models import DailyPlan, Transaction, User
from app.services.spending_prevention_service import SpendingPreventionService

# --------------------------------------------------------------------------
# Pure mapping — no database needed.
# --------------------------------------------------------------------------


def test_food_covers_the_planner_s_food_buckets():
    wanted = plan_categories_for("food")
    assert {"groceries", "dining out", "coffee"} <= wanted


def test_transportation_covers_both_transport_buckets():
    wanted = plan_categories_for("transportation")
    assert {"transport public", "transport gas"} <= wanted


def test_category_always_matches_itself():
    # A caller already speaking the plan vocabulary must keep working, and an
    # unmapped/custom category must still find its own row.
    assert matches_category("groceries", "groceries")
    assert matches_category("some custom bucket", "some custom bucket")


def test_lookup_is_case_and_whitespace_insensitive():
    assert matches_category("Groceries", "  FOOD ")


def test_unrelated_categories_do_not_match():
    assert not matches_category("rent", "food")
    assert not matches_category("groceries", "transportation")


# --------------------------------------------------------------------------
# End to end through the service, against the real plan vocabulary.
# --------------------------------------------------------------------------


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
        email=f"aliases_{uuid4().hex[:10]}@mita.app",
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
def planned_day(db_session, user):
    """Exactly what onboarding produced for the device-reproduced case."""
    today = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    for category, budget in [
        ("coffee", "5.40"),
        ("groceries", "13.71"),
        ("transport public", "30.00"),
    ]:
        db_session.add(
            DailyPlan(
                id=uuid4(),
                user_id=user.id,
                date=today,
                category=category,
                planned_amount=Decimal(budget),
                daily_budget=Decimal(budget),
                spent_amount=Decimal("0.00"),
                status="green",
            )
        )
    db_session.commit()
    return today


def test_food_no_longer_reports_no_budget(db_session, user, planned_day):
    result = SpendingPreventionService(db_session, user.id).check_affordability(
        category="food", amount=Decimal("5.00"), transaction_date=planned_day
    )

    assert "No budget set" not in result["impact_message"]
    # coffee 5.40 + groceries 13.71 — the buckets "food" actually spends from.
    assert result["daily_budget"] == pytest.approx(19.11)
    assert result["remaining_budget"] == pytest.approx(14.11)
    assert result["can_afford"] is True


def test_transportation_aggregates_its_buckets(db_session, user, planned_day):
    result = SpendingPreventionService(db_session, user.id).check_affordability(
        category="transportation",
        amount=Decimal("5.00"),
        transaction_date=planned_day,
    )
    assert result["daily_budget"] == pytest.approx(30.00)
    assert "No budget set" not in result["impact_message"]


def test_spend_on_one_bucket_counts_against_the_alias(db_session, user, planned_day):
    row = (
        db_session.query(DailyPlan)
        .filter_by(user_id=user.id, category="groceries")
        .one()
    )
    row.spent_amount = Decimal("10.00")
    db_session.commit()

    result = SpendingPreventionService(db_session, user.id).check_affordability(
        category="food", amount=Decimal("5.00"), transaction_date=planned_day
    )
    assert result["current_spent"] == pytest.approx(10.00)
    assert result["remaining_budget"] == pytest.approx(4.11)


def test_category_with_no_bucket_today_still_reports_no_budget(
    db_session, user, planned_day
):
    # Truthful in the other direction: the planner clusters entertainment on
    # specific days, so "no budget today" is the correct answer here.
    result = SpendingPreventionService(db_session, user.id).check_affordability(
        category="entertainment",
        amount=Decimal("5.00"),
        transaction_date=planned_day,
    )
    assert "No budget set" in result["impact_message"]

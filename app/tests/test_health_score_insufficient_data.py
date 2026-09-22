"""A Financial Health Score must be measured, not derived from an income tier.

`AIFinancialAnalyzer.calculate_financial_health_score()` answered a user with
NO transactions at all with the income tier's *expectation* threshold —
`component_expectations["budgeting_excellence"]`, which is 70 plus a tier bonus
of -5 (low) to +5 (high) — presented as that person's score:

    monthly income 2500  -> score 68, grade "C+"
    monthly income 5000  -> score 73, grade "C"
    monthly income 9000  -> score 73, grade "C"
    monthly income 20000 -> score 75, grade "C"

with the same number copied into four components (`budgeting`, `saving`,
`debt_management`, `spending_efficiency` — two of which the real calculation
never produces), and `trend: "stable"`. Reproduced end to end through
GET /api/ai/financial-health-score on a brand-new account.

`insights_screen._buildFinancialHealthCard` renders "Add more transactions to
calculate your financial health score" only when score/grade are null, so this
branch was exactly what stopped the honest empty state from ever appearing.

The contract pinned here:

* no usable ledger data (no transactions, or only deleted / out-of-window
  ones) -> score None, grade None, components {}, trend None, plus
  `status: "insufficient_data"`. No substitute figure, from the income tier or
  anywhere else;
* a user who HAS spending still gets the real calculation, with its own
  component names.

Requires: PostgreSQL at DATABASE_URL with migrations at head.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db.models import Transaction, User
from app.services.ai_financial_analyzer import AIFinancialAnalyzer

# The tier baselines the removed branch published, by monthly income. Written
# out by hand from dynamic_threshold_service._get_budgeting_threshold
# (70 + {low -5, lower_middle -2, middle 0, upper_middle +3, high +5}).
TIER_BASELINE = {
    "2500.00": 65,
    "4000.00": 68,
    "6000.00": 70,
    "9000.00": 73,
    "20000.00": 75,
}
# Every figure that branch could put on screen, whatever the tier.
FABRICATED_SCORES = set(TIER_BASELINE.values())
# Component names only the synthetic branch ever produced.
SYNTHETIC_COMPONENTS = {"saving", "debt_management"}
REAL_COMPONENTS = {
    "budgeting",
    "spending_efficiency",
    "saving_potential",
    "consistency",
}
GRADES = {"A+", "A", "B+", "B", "C+", "C", "D+", "D", "F"}

NOW = datetime.now(timezone.utc)


@pytest.fixture
def db():
    """One transaction, rolled back: nothing here is committed."""
    from sqlalchemy.orm import Session as OrmSession

    import app.core.session as session_module

    gen = session_module.get_db()
    next(gen)  # initialises the engine
    connection = session_module.engine.connect()
    outer = connection.begin()
    session = OrmSession(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        outer.rollback()
        connection.close()
        gen.close()


def _user(db, income, spends=(), *, days_ago=1, deleted=False):
    user = User(
        id=uuid4(),
        email=f"health_{uuid4().hex[:12]}@mita.app",
        password_hash="x",
        has_onboarded=True,
        timezone="UTC",
        monthly_income=Decimal(str(income)),
    )
    db.add(user)
    db.flush()
    for i, amount in enumerate(spends):
        db.add(
            Transaction(
                id=uuid4(),
                user_id=user.id,
                category=("food", "transport", "shopping")[i % 3],
                amount=Decimal(str(amount)),
                spent_at=NOW - timedelta(days=days_ago),
                deleted_at=NOW if deleted else None,
            )
        )
    db.flush()
    return user


def _score(db, user):
    return AIFinancialAnalyzer(db, user.id).calculate_financial_health_score()


def _numbers_in(payload):
    """Every number the payload states, at any depth."""
    found = []
    stack = [payload]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            stack.extend(item.values())
        elif isinstance(item, (list, tuple)):
            stack.extend(item)
        elif isinstance(item, bool):
            continue
        elif isinstance(item, (int, float)):
            found.append(item)
    return found


def _assert_no_assessment(data):
    assert data["score"] is None, data
    assert data["grade"] is None, data
    assert data["components"] == {}, data
    assert data["trend"] is None, data
    assert data["status"] == "insufficient_data", data
    # Not one of the tier baselines, anywhere, under any key.
    assert not FABRICATED_SCORES & set(_numbers_in(data)), data


# ---------------------------------------------------------------------------
# No ledger at all
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("income", sorted(TIER_BASELINE))
def test_a_user_with_no_transactions_gets_no_score_in_any_tier(db, income):
    """The tier decided the old score; it must decide nothing now."""
    _assert_no_assessment(_score(db, _user(db, income)))


def test_the_score_does_not_vary_with_income_when_there_is_no_data(db):
    """Two incomes, two different old scores (65 and 75), same answer now."""
    poorest = _score(db, _user(db, "2500.00"))
    richest = _score(db, _user(db, "20000.00"))
    assert poorest == richest


def test_the_synthetic_component_names_are_gone(db):
    data = _score(db, _user(db, "9000.00"))
    assert not SYNTHETIC_COMPONENTS & set(data["components"])


def test_guidance_is_still_offered(db):
    """Suppressing the verdict must not suppress the "what to do" copy."""
    data = _score(db, _user(db, "9000.00"))
    assert data["improvements"] == [
        "Start tracking expenses to get accurate health score"
    ]


# ---------------------------------------------------------------------------
# A ledger that holds nothing usable is the same as no ledger
# ---------------------------------------------------------------------------
def test_only_deleted_transactions_is_insufficient(db):
    user = _user(db, "9000.00", ["120.00", "80.00"], deleted=True)
    _assert_no_assessment(_score(db, user))


def test_only_transactions_older_than_the_window_is_insufficient(db):
    """_load_spending_data looks back 6 months; older rows are not data."""
    user = _user(db, "9000.00", ["120.00", "80.00"], days_ago=200)
    _assert_no_assessment(_score(db, user))


# ---------------------------------------------------------------------------
# Real data still gets the real calculation
# ---------------------------------------------------------------------------
def test_a_user_with_spending_still_gets_a_measured_score(db):
    user = _user(db, "9000.00", [str(40 + i) for i in range(40)])
    data = _score(db, user)

    assert isinstance(data["score"], int)
    assert 0 <= data["score"] <= 100
    assert data["grade"] in GRADES
    assert set(data["components"]) == REAL_COMPONENTS
    assert data.get("status") != "insufficient_data"


def test_one_transaction_is_enough_to_measure(db):
    """The fix suppresses only what nothing measured, not sparse ledgers."""
    data = _score(db, _user(db, "9000.00", ["57.30"]))
    assert isinstance(data["score"], int)
    assert data["grade"] in GRADES


def test_the_measured_score_tracks_the_ledger(db):
    """Same income tier, two different ledgers, two different answers.

    The old branch could only ever say 75 for this tier; a measured score
    moves with what the person actually spent.
    """
    frugal = _score(db, _user(db, "20000.00", [str(10 + i) for i in range(40)]))
    heavy = _score(db, _user(db, "20000.00", [str(900 + i * 50) for i in range(40)]))
    assert frugal["score"] != heavy["score"], (frugal, heavy)


# ---------------------------------------------------------------------------
# End to end through the route the app actually calls
# ---------------------------------------------------------------------------
@pytest.fixture
def client():
    from app.main import app

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def _get(client, db, user):
    from app.api.dependencies import get_current_user
    from app.core.async_session import get_async_db
    from app.main import app

    subject = SimpleNamespace(
        id=user.id, email=user.email, is_premium=True, timezone="UTC"
    )
    async_db = Mock()
    async_db.run_sync = AsyncMock(side_effect=lambda fn: fn(db))
    app.dependency_overrides[get_current_user] = lambda: subject
    app.dependency_overrides[get_async_db] = lambda: async_db
    try:
        resp = client.get("/api/ai/financial-health-score")
        assert resp.status_code == 200, resp.text
        return resp.json()["data"]
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_async_db, None)


def test_route_states_no_score_for_a_brand_new_account(client, db):
    """The reproduction: a fresh account was told 73 / "C"."""
    _assert_no_assessment(_get(client, db, _user(db, "9000.00")))


def test_route_still_answers_200_with_no_data(client, db):
    """Honesty must not cost the screen its response."""
    from app.api.dependencies import get_current_user
    from app.core.async_session import get_async_db
    from app.main import app

    user = _user(db, "9000.00")
    subject = SimpleNamespace(
        id=user.id, email=user.email, is_premium=True, timezone="UTC"
    )
    async_db = Mock()
    async_db.run_sync = AsyncMock(side_effect=lambda fn: fn(db))
    app.dependency_overrides[get_current_user] = lambda: subject
    app.dependency_overrides[get_async_db] = lambda: async_db
    try:
        assert client.get("/api/ai/financial-health-score").status_code == 200
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_async_db, None)


def test_route_publishes_a_real_score_when_there_is_spending(client, db):
    user = _user(db, "9000.00", [str(40 + i) for i in range(40)])
    data = _get(client, db, user)

    assert isinstance(data["score"], int)
    assert data["grade"] in GRADES
    assert set(data["components"]) == REAL_COMPONENTS

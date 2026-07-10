"""Regression: /api/cohort/insights and /income_classification 500'd with a
Decimal/float TypeError when the user had transactions.

Transaction.amount is Decimal; the routes mixed it with float income/peer
literals ("unsupported operand type(s) for -: 'decimal.Decimal' and 'float'"),
500-ing on every onboarded user with spending and firing the mobile
"Server error" toast.

Requires: PostgreSQL at DATABASE_URL (test_mita) with migrations at head.
"""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db.models import Transaction, User


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
        email=f"cohort_{uuid4().hex[:10]}@mita.app",
        password_hash="x",
        has_onboarded=True,
        timezone="UTC",
        monthly_income=Decimal("6000.00"),
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    # Seed Decimal-amount transactions (the shape that triggered the crash).
    for amt, cat in [("42.00", "food"), ("100.00", "transport"), ("18.50", "food")]:
        db_session.add(
            Transaction(
                user_id=u.id,
                category=cat,
                amount=Decimal(amt),
                currency="USD",
                spent_at=datetime.now(timezone.utc),
            )
        )
    db_session.commit()
    yield u
    db_session.query(Transaction).filter_by(user_id=u.id).delete()
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


def test_cohort_insights_with_decimal_spending(authed):
    resp = authed.get("/api/cohort/insights")
    assert resp.status_code == 200, resp.text
    assert "cohort_type" in resp.json()["data"]


def test_income_classification_with_decimal_spending(authed):
    resp = authed.get("/api/cohort/income_classification")
    assert resp.status_code == 200, resp.text
    assert "income_tier" in resp.json()["data"]

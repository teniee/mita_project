"""Every production writer of a Transaction must go through the ledger.

A writer that inserts a Transaction and commits it itself records spend in
the transaction list that the daily plan never sees: no advisory lock, no
month rebuild, no redistribution. The dashboard, the calendar and the alerts
then disagree with the ledger, and the disagreement is silent.

These are the paths that used to bypass it:
  * POST /api/expense/add            (app/api/expense/routes.py)
  * goal auto-transfer to savings    (app/services/goal_budget_integration.py)

app/tests/test_transactions_crud_integration.py covers /api/transactions.

Requires: PostgreSQL at DATABASE_URL (test_mita) with migrations at head.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db.models import DailyPlan, Goal, Transaction, User
from app.services.core.engine.expense_tracker import local_day_of


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


def _make_user(db_session, timezone_name="Europe/Sofia"):
    user = User(
        id=uuid4(),
        email=f"ledger_path_{uuid4().hex[:10]}@mita.app",
        password_hash="hashed_password_123",
        has_onboarded=True,
        timezone=timezone_name,
        monthly_income=Decimal("6000.00"),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _cleanup(db_session, user):
    db_session.query(Transaction).filter_by(user_id=user.id).delete()
    db_session.query(DailyPlan).filter_by(user_id=user.id).delete()
    db_session.query(Goal).filter_by(user_id=user.id).delete()
    db_session.query(User).filter_by(id=user.id).delete()
    db_session.commit()


@pytest.fixture
def user_a(db_session):
    user = _make_user(db_session)
    yield user
    _cleanup(db_session, user)


@pytest.fixture
def user_b(db_session):
    user = _make_user(db_session)
    yield user
    _cleanup(db_session, user)


@pytest.fixture
def as_user(client, user_a):
    from app.api.dependencies import get_current_user
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: user_a
    try:
        yield client
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def _expense_payload(user, action, amount):
    """ExpenseEntry requires user_id and date; the route re-derives both from
    the authenticated user, but the schema still validates them."""
    return {
        "user_id": str(user.id),
        "action": action,
        "amount": amount,
        "date": datetime.now(timezone.utc).date().isoformat(),
    }


def _plan_row(db_session, user, day, category):
    db_session.expire_all()
    rows = [
        row
        for row in db_session.query(DailyPlan)
        .filter(DailyPlan.user_id == user.id, DailyPlan.category == category)
        .all()
        if (row.date.date() if hasattr(row.date, "date") else row.date) == day
    ]
    return rows[0] if rows else None


class TestExpenseAddEndpoint:
    """POST /api/expense/add used to commit a Transaction with no plan."""

    def test_expense_add_applies_to_daily_plan(self, as_user, db_session, user_a):
        resp = as_user.post(
            "/api/expense/add",
            json=_expense_payload(user_a, "food", 37.50),
        )
        assert resp.status_code in (200, 201), resp.text

        txns = (
            db_session.query(Transaction).filter(Transaction.user_id == user_a.id).all()
        )
        # Created exactly once — not zero, and not duplicated by a retry.
        assert len(txns) == 1
        txn = txns[0]
        assert Decimal(txn.amount) == Decimal("37.50")

        day = local_day_of(txn.spent_at, user_a.timezone)
        plan = _plan_row(db_session, user_a, day, txn.category)
        assert plan is not None, (
            "expense/add left no DailyPlan row - the spend is invisible to "
            "the budget"
        )
        assert Decimal(plan.spent_amount) == Decimal("37.50")

    def test_expense_add_matches_transactions_endpoint(
        self, as_user, db_session, user_a
    ):
        """Both writers must land the same spend in the same bucket."""
        as_user.post("/api/expense/add", json=_expense_payload(user_a, "food", 10.00))
        as_user.post(
            "/api/transactions/",
            json={
                "amount": 10.00,
                "category": "food",
                "description": "via transactions",
                "spent_at": datetime.now(timezone.utc).isoformat(),
            },
        )

        db_session.expire_all()
        txns = (
            db_session.query(Transaction).filter(Transaction.user_id == user_a.id).all()
        )
        assert len(txns) == 2
        day = local_day_of(txns[0].spent_at, user_a.timezone)
        plan = _plan_row(db_session, user_a, day, "food")
        assert plan is not None
        assert Decimal(plan.spent_amount) == Decimal("20.00")

    def test_plan_failure_rolls_back_the_transaction(
        self, as_user, db_session, user_a, monkeypatch
    ):
        """A failing rebuild must not leave a committed orphan transaction."""
        import app.services.core.engine.expense_tracker as tracker

        def _boom(*args, **kwargs):
            raise RuntimeError("injected plan rebuild failure")

        monkeypatch.setattr(tracker, "rebuild_month_plan", _boom)

        resp = as_user.post(
            "/api/expense/add",
            json=_expense_payload(user_a, "food", 55.00),
        )
        assert resp.status_code >= 400, resp.text

        db_session.expire_all()
        assert (
            db_session.query(Transaction)
            .filter(Transaction.user_id == user_a.id)
            .count()
            == 0
        ), "transaction survived a failed plan rebuild"


class TestGoalAutoTransfer:
    """Goal auto-transfer used to commit a savings Transaction with no plan."""

    def test_auto_transfer_applies_to_daily_plan(self, db_session, user_a):
        from app.services.goal_budget_integration import get_goal_budget_integration

        goal = Goal(
            id=uuid4(),
            user_id=user_a.id,
            title="Emergency fund",
            target_amount=Decimal("1000.00"),
            saved_amount=Decimal("0.00"),
            status="active",
        )
        db_session.add(goal)
        db_session.commit()

        result = get_goal_budget_integration(db_session).auto_transfer_to_savings_goal(
            user_a.id, goal.id, Decimal("125.00")
        )
        assert result.get("success") is True, result

        db_session.expire_all()
        txns = (
            db_session.query(Transaction).filter(Transaction.user_id == user_a.id).all()
        )
        assert len(txns) == 1
        txn = txns[0]

        day = local_day_of(txn.spent_at, user_a.timezone)
        plan = _plan_row(db_session, user_a, day, txn.category)
        assert plan is not None, (
            "goal auto-transfer left no DailyPlan row - savings never reach "
            "the budget"
        )
        assert Decimal(plan.spent_amount) == Decimal("125.00")

        # Goal progress and the ledger move together.
        db_session.refresh(goal)
        assert Decimal(goal.saved_amount) == Decimal("125.00")


class TestLedgerConcurrency:
    """The advisory lock must cover the mutation, not just precede it."""

    def test_same_user_writes_serialize(self, client, db_session, user_a):
        from app.api.dependencies import get_current_user
        from app.main import app

        app.dependency_overrides[get_current_user] = lambda: user_a

        def _post(amount):
            return client.post(
                "/api/expense/add",
                json=_expense_payload(user_a, "food", amount),
            ).status_code

        try:
            with ThreadPoolExecutor(max_workers=4) as pool:
                codes = list(pool.map(_post, [11.00, 12.00, 13.00, 14.00]))
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert all(code in (200, 201) for code in codes), codes

        db_session.expire_all()
        txns = (
            db_session.query(Transaction).filter(Transaction.user_id == user_a.id).all()
        )
        assert len(txns) == 4
        day = local_day_of(txns[0].spent_at, user_a.timezone)
        plan = _plan_row(db_session, user_a, day, "food")
        assert plan is not None
        # No lost update: every concurrent write is accounted for.
        assert Decimal(plan.spent_amount) == Decimal("50.00")

    def test_unrelated_users_do_not_block_each_other(
        self, client, db_session, user_a, user_b
    ):
        from app.api.dependencies import get_current_user
        from app.main import app

        def _post_as(user, amount):
            app.dependency_overrides[get_current_user] = lambda: user
            try:
                return client.post(
                    "/api/expense/add",
                    json=_expense_payload(user, "food", amount),
                ).status_code
            finally:
                app.dependency_overrides.pop(get_current_user, None)

        assert _post_as(user_a, 21.00) in (200, 201)
        assert _post_as(user_b, 22.00) in (200, 201)

        db_session.expire_all()
        for user, expected in ((user_a, "21.00"), (user_b, "22.00")):
            txns = (
                db_session.query(Transaction)
                .filter(Transaction.user_id == user.id)
                .all()
            )
            assert len(txns) == 1
            day = local_day_of(txns[0].spent_at, user.timezone)
            plan = _plan_row(db_session, user, day, "food")
            assert plan is not None
            assert Decimal(plan.spent_amount) == Decimal(expected)

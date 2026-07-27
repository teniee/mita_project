"""Money precision and post-commit side-effect contract for the ledger.

Two invariants:

1. Money never round-trips through binary floating point on a write path.
   Transaction.amount, goal progress and the API payload must all carry the
   exact decimal the caller asked for.

2. The ledger commit is authoritative. Once the Transaction and its DailyPlan
   rows are durable, a failing notification/alert must not turn the mutation
   into an error - that would invite a client retry and duplicate the spend.

Requires: PostgreSQL at DATABASE_URL (test_mita) with migrations at head.
"""

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


@pytest.fixture
def user_a(db_session):
    user = User(
        id=uuid4(),
        email=f"ledger_money_{uuid4().hex[:10]}@mita.app",
        password_hash="x",
        has_onboarded=True,
        timezone="Europe/Sofia",
        monthly_income=Decimal("6000.00"),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    yield user
    db_session.query(Transaction).filter_by(user_id=user.id).delete()
    db_session.query(DailyPlan).filter_by(user_id=user.id).delete()
    db_session.query(Goal).filter_by(user_id=user.id).delete()
    db_session.query(User).filter_by(id=user.id).delete()
    db_session.commit()


@pytest.fixture
def as_user(client, user_a):
    from app.api.dependencies import get_current_user
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: user_a
    try:
        yield client
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def _plan_row(db_session, user, day, category):
    db_session.expire_all()
    for row in (
        db_session.query(DailyPlan)
        .filter(DailyPlan.user_id == user.id, DailyPlan.category == category)
        .all()
    ):
        row_day = row.date.date() if hasattr(row.date, "date") else row.date
        if row_day == day:
            return row
    return None


def _new_goal(db_session, user):
    goal = Goal(
        id=uuid4(),
        user_id=user.id,
        title="Precision fund",
        target_amount=Decimal("1000.00"),
        saved_amount=Decimal("0.00"),
        status="active",
    )
    db_session.add(goal)
    db_session.commit()
    return goal


class TestMoneyPrecision:
    """No monetary value may pass through float on a write path."""

    @pytest.mark.parametrize(
        "amount",
        [
            Decimal("0.01"),  # smallest representable cent
            Decimal("10.05"),  # float(10.05) == 10.05000000000000071...
            Decimal("100.10"),  # float(100.10) == 100.09999999999999432...
            Decimal("0.07"),
        ],
    )
    def test_goal_transfer_stores_exact_decimal(self, db_session, user_a, amount):
        from app.services.goal_budget_integration import get_goal_budget_integration

        goal = _new_goal(db_session, user_a)
        result = get_goal_budget_integration(db_session).auto_transfer_to_savings_goal(
            user_a.id, goal.id, amount
        )
        assert result.get("success") is True, result

        db_session.expire_all()
        txn = (
            db_session.query(Transaction).filter(Transaction.user_id == user_a.id).one()
        )
        # Exact decimal equality — not pytest.approx.
        assert Decimal(txn.amount) == amount
        assert Decimal(txn.amount).as_tuple().exponent >= -2

        db_session.refresh(goal)
        assert Decimal(goal.saved_amount) == amount

        day = local_day_of(txn.spent_at, user_a.timezone)
        plan = _plan_row(db_session, user_a, day, txn.category)
        assert plan is not None
        assert Decimal(plan.spent_amount) == amount

    def test_negative_input_is_normalised_to_positive_savings(self, db_session, user_a):
        from app.services.goal_budget_integration import get_goal_budget_integration

        goal = _new_goal(db_session, user_a)
        result = get_goal_budget_integration(db_session).auto_transfer_to_savings_goal(
            user_a.id, goal.id, Decimal("-10.05")
        )
        assert result.get("success") is True, result

        db_session.expire_all()
        txn = (
            db_session.query(Transaction).filter(Transaction.user_id == user_a.id).one()
        )
        assert Decimal(txn.amount) == Decimal("10.05")

        db_session.refresh(goal)
        # Goal progress must advance by the stored value, not the raw input.
        assert Decimal(goal.saved_amount) == Decimal("10.05")
        # And the payload must report what was persisted.
        assert result["amount"] == pytest.approx(10.05)
        assert result["new_saved_amount"] == pytest.approx(10.05)

    def test_repeated_transfers_do_not_accumulate_drift(self, db_session, user_a):
        """20 x 0.07 must be exactly 1.40, not 1.3999999999999997."""
        from app.services.goal_budget_integration import get_goal_budget_integration

        goal = _new_goal(db_session, user_a)
        service = get_goal_budget_integration(db_session)
        for _ in range(20):
            assert (
                service.auto_transfer_to_savings_goal(
                    user_a.id, goal.id, Decimal("0.07")
                ).get("success")
                is True
            )

        db_session.expire_all()
        db_session.refresh(goal)
        assert Decimal(goal.saved_amount) == Decimal("1.40")

        total = sum(
            (
                Decimal(t.amount)
                for t in db_session.query(Transaction)
                .filter(Transaction.user_id == user_a.id)
                .all()
            ),
            Decimal("0.00"),
        )
        assert total == Decimal("1.40")


class TestPostCommitSideEffects:
    """A committed ledger mutation must survive a failing alert."""

    def test_side_effect_failure_still_returns_success_exactly_once(
        self, as_user, db_session, user_a, monkeypatch
    ):
        import app.services.core.engine.expense_tracker as tracker

        calls = {"n": 0}

        def _boom(db, txn, rebalance_result=None):
            calls["n"] += 1
            raise RuntimeError("injected post-commit alert failure")

        # Fail the inner implementation; the public wrapper must absorb it.
        monkeypatch.setattr(tracker, "_run_transaction_plan_side_effects", _boom)

        resp = as_user.post(
            "/api/transactions/",
            json={
                "amount": 42.00,
                "category": "food",
                "description": "side effect failure",
                "spent_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        # The mutation succeeded — reporting 5xx here would make the client
        # retry and record the same spend twice.
        assert resp.status_code in (200, 201), resp.text
        assert calls["n"] >= 1, "side effects were never attempted"

        db_session.expire_all()
        txns = (
            db_session.query(Transaction).filter(Transaction.user_id == user_a.id).all()
        )
        assert len(txns) == 1, "transaction was duplicated or lost"
        assert Decimal(txns[0].amount) == Decimal("42.00")

        day = local_day_of(txns[0].spent_at, user_a.timezone)
        plan = _plan_row(db_session, user_a, day, "food")
        assert plan is not None, "DailyPlan missing after side-effect failure"
        assert Decimal(plan.spent_amount) == Decimal("42.00")

    def test_pre_commit_failure_still_raises(
        self, as_user, db_session, user_a, monkeypatch
    ):
        """Only post-commit work is best-effort; ledger errors stay loud."""
        import app.services.core.engine.expense_tracker as tracker

        def _boom(*args, **kwargs):
            raise RuntimeError("injected pre-commit ledger failure")

        monkeypatch.setattr(tracker, "rebuild_month_plan", _boom)

        resp = as_user.post(
            "/api/transactions/",
            json={
                "amount": 77.00,
                "category": "food",
                "description": "pre commit failure",
                "spent_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        assert resp.status_code >= 400, resp.text

        db_session.expire_all()
        assert (
            db_session.query(Transaction)
            .filter(Transaction.user_id == user_a.id)
            .count()
            == 0
        ), "a pre-commit failure must roll the transaction back"

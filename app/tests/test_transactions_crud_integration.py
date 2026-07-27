"""Integration regressions for the transaction CRUD core journey.

These tests drive the REAL FastAPI routes through TestClient with the real
async DB dependency (`get_async_db`) against PostgreSQL — the wiring that the
sync-fixture unit tests never exercised, which is how DEF-001 ("AsyncSession
has no attribute 'query'" → HTTP 500 on list/get/update/delete) shipped green.

Covered regressions:
- DEF-001: list / get / update / delete return 200 through the async DI.
- DEF-002: PUT body validation accepts valid amounts, 422s invalid ones.
- N-P1-DASH-SOFTDELETE (V1): dashboard aggregations exclude soft-deleted
  transactions — exact balance numbers, not just HTTP status.
- INV-13: editing an amount replaces (not double-adds) the daily-plan accrual.
- INV-14: deleting reverses the daily-plan accrual.
- Ownership: user B gets 404 on A's transaction for GET/PUT/DELETE and never
  sees A's rows in a list.

Requires: PostgreSQL at DATABASE_URL (test_mita) with migrations at head.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal
from queue import Queue
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from app.db.models import DailyPlan, RedistributionEvent, Transaction, User
from app.services.core.engine.expense_tracker import (
    lock_user_ledger,
    rebuild_month_plan,
)


@pytest.fixture
def client():
    from app.main import app

    # Context manager keeps ONE portal event loop for all requests in a test;
    # asyncpg pool connections are loop-bound, so per-request loops would make
    # the second async request fail with "attached to a different loop".
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


def _make_user(db_session, monthly_income="6000.00"):
    user = User(
        id=uuid4(),
        email=f"txn_crud_{uuid4().hex[:10]}@mita.app",
        password_hash="hashed_password_123",
        has_onboarded=True,
        timezone="UTC",
        monthly_income=Decimal(monthly_income),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _cleanup_user(db_session, user):
    db_session.query(Transaction).filter_by(user_id=user.id).delete()
    db_session.query(DailyPlan).filter_by(user_id=user.id).delete()
    db_session.query(User).filter_by(id=user.id).delete()
    db_session.commit()


@pytest.fixture
def user_a(db_session):
    user = _make_user(db_session)
    yield user
    _cleanup_user(db_session, user)


@pytest.fixture
def user_b(db_session):
    user = _make_user(db_session)
    yield user
    _cleanup_user(db_session, user)


@pytest.fixture
def as_user_a(client, user_a):
    from app.api.dependencies import get_current_user
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: user_a
    try:
        yield client
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def _auth_as(user):
    from app.api.dependencies import get_current_user
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: user


def _create_txn(client, amount="42.00", category="food", spent_at=None):
    resp = client.post(
        "/api/transactions/",
        json={
            "amount": float(amount),
            "category": category,
            "description": "integration txn",
            "spent_at": (spent_at or datetime.now(timezone.utc)).isoformat(),
        },
    )
    assert resp.status_code in (200, 201), resp.text
    body = resp.json()
    assert "_mita_rebalance_plan" not in resp.text
    data = body.get("data", body)
    txn = data.get("transaction", data)
    txn_id = txn.get("id") or txn.get("transaction_id")
    assert txn_id, f"no transaction id in response: {body}"
    return str(txn_id)


def _dashboard_numbers(client):
    resp = client.get("/api/dashboard")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    return float(data["balance"]), float(data["spent"])


class TestTransactionCrudAsyncWiring:
    """DEF-001: every CRUD verb must survive the real AsyncSession DI."""

    def test_create_without_description_is_201(self, as_user_a, db_session, user_a):
        """Description is optional (TxnIn, DB column, mobile form) — the
        create route 422'd on it (device-reproduced: every description-less
        add-expense failed with VALIDATION_2001)."""
        resp = as_user_a.post(
            "/api/transactions/",
            json={
                "amount": 5.00,
                "category": "food",
                "spent_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        assert resp.status_code in (200, 201), resp.text
        assert resp.json()["data"]["rebalanced"] is False

    def test_full_crud_roundtrip(self, as_user_a, db_session, user_a):
        txn_id = _create_txn(as_user_a)

        # LIST — 500 before the fix
        resp = as_user_a.get("/api/transactions/")
        assert resp.status_code == 200, resp.text
        listed = resp.json()["data"]
        if isinstance(listed, dict):
            listed = listed.get("transactions", listed)
        assert any(str(t["id"]) == txn_id for t in listed)

        # GET by id — 500 before the fix
        resp = as_user_a.get(f"/api/transactions/{txn_id}")
        assert resp.status_code == 200, resp.text

        # UPDATE — 500 before the fix (DEF-001 + DEF-002)
        resp = as_user_a.put(f"/api/transactions/{txn_id}", json={"amount": 100.00})
        assert resp.status_code == 200, resp.text
        db_session.expire_all()
        stored = db_session.get(Transaction, txn_id)
        assert stored.amount == Decimal("100.00")

        # DELETE — 500 before the fix
        resp = as_user_a.delete(f"/api/transactions/{txn_id}")
        assert resp.status_code == 200, resp.text
        db_session.expire_all()
        stored = db_session.get(Transaction, txn_id)
        assert stored.deleted_at is not None  # soft-deleted, not erased

        # Deleted txn disappears from list and get
        resp = as_user_a.get("/api/transactions/")
        assert resp.status_code == 200
        listed = resp.json()["data"]
        if isinstance(listed, dict):
            listed = listed.get("transactions", listed)
        assert not any(str(t["id"]) == txn_id for t in listed)
        assert as_user_a.get(f"/api/transactions/{txn_id}").status_code == 404

    def test_invalid_uuid_is_4xx_not_500(self, as_user_a):
        for verb, path in (
            ("get", "/api/transactions/not-a-uuid"),
            ("delete", "/api/transactions/not-a-uuid"),
        ):
            resp = getattr(as_user_a, verb)(path)
            assert 400 <= resp.status_code < 500, f"{verb}: {resp.status_code}"
        resp = as_user_a.put("/api/transactions/not-a-uuid", json={"amount": 10})
        assert 400 <= resp.status_code < 500

    def test_put_invalid_amount_is_422_not_500(self, as_user_a):
        txn_id = _create_txn(as_user_a)
        for bad in (-5, 0, "abc", "NaN", 2_000_000):
            resp = as_user_a.put(f"/api/transactions/{txn_id}", json={"amount": bad})
            assert resp.status_code == 422, f"{bad}: {resp.status_code} {resp.text}"


class TestFinancialRecalculation:
    """Exact-number invariants INV-12/13/14 + V1 (soft-delete aggregation)."""

    def test_create_runs_rebalance_once_and_preserves_donor_cap(
        self, as_user_a, db_session, user_a
    ):
        transaction_month = self._previous_month(datetime.now(timezone.utc).date())
        transaction_day = transaction_month.replace(day=10)
        donor_day = transaction_month.replace(day=20)
        db_session.add_all(
            [
                self._new_plan(user_a, transaction_day, "food", "0.00"),
                self._new_plan(user_a, donor_day, "shopping", "100.00"),
            ]
        )
        db_session.commit()

        _create_txn(
            as_user_a,
            amount="100.00",
            category="food",
            spent_at=datetime(
                transaction_day.year,
                transaction_day.month,
                transaction_day.day,
                12,
                tzinfo=timezone.utc,
            ),
        )

        # One rebalance may take at most 50% from the donor. The create route
        # previously ran a second pass and reduced 100 -> 50 -> 25.
        assert self._plan_values(db_session, user_a, transaction_day, "food") == (
            Decimal("50.00"),
            Decimal("50.00"),
            Decimal("100.00"),
        )
        assert self._plan_values(db_session, user_a, donor_day, "shopping")[:2] == (
            Decimal("50.00"),
            Decimal("50.00"),
        )

    def test_post_commit_alert_uses_pre_rebalance_limit(
        self, as_user_a, db_session, user_a, monkeypatch
    ):
        transaction_month = self._previous_month(datetime.now(timezone.utc).date())
        transaction_day = transaction_month.replace(day=10)
        donor_day = transaction_month.replace(day=20)
        db_session.add_all(
            [
                self._new_plan(user_a, transaction_day, "food", "10.00"),
                self._new_plan(user_a, donor_day, "shopping", "100.00"),
            ]
        )
        db_session.commit()

        captured = {}

        class AlertRecorder:
            def check_single_category(
                self,
                *,
                user_id,
                category,
                spent_amount,
                budget_limit,
            ):
                captured.update(
                    {
                        "user_id": user_id,
                        "category": category,
                        "spent": Decimal(spent_amount),
                        "limit": Decimal(budget_limit),
                    }
                )

        monkeypatch.setattr(
            "app.services.budget_alert_service.get_budget_alert_service",
            lambda db: AlertRecorder(),
        )
        monkeypatch.setattr(
            "app.services.velocity_alert_service.check_velocity_after_transaction",
            lambda **kwargs: None,
        )

        response = as_user_a.post(
            "/api/transactions/",
            json={
                "amount": 30.00,
                "category": "food",
                "description": "alert limit regression",
                "spent_at": datetime(
                    transaction_day.year,
                    transaction_day.month,
                    transaction_day.day,
                    12,
                    tzinfo=timezone.utc,
                ).isoformat(),
            },
        )
        assert response.status_code == 201, response.text
        response_transaction = response.json()["data"]
        assert response_transaction["rebalanced"] is True
        assert response_transaction["rebalance_covered"] == 20.0
        assert response_transaction["rebalance_fully_covered"] is True

        assert captured == {
            "user_id": user_a.id,
            "category": "food",
            "spent": Decimal("30.00"),
            "limit": Decimal("10.00"),
        }

    def test_rebalance_allocations_reverse_across_full_crud_journey(
        self, as_user_a, db_session, user_a
    ):
        """Every transaction mutation must undo its prior redistribution before
        applying the replacement ledger state.

        This is the production device journey that exposed stale planned
        amounts on the old category/day/month after edit, move, and delete.
        """
        first_month = self._previous_month(datetime.now(timezone.utc).date())
        second_month = self._previous_month(first_month)

        original_day = second_month.replace(day=11)
        previous_day = second_month.replace(day=10)
        original_donor_day = second_month.replace(day=20)
        next_month_day = first_month.replace(day=10)
        next_month_donor_day = first_month.replace(day=20)

        plans = [
            self._new_plan(user_a, previous_day, "entertainment", "5.00"),
            self._new_plan(user_a, original_day, "food", "10.00"),
            self._new_plan(user_a, original_day, "entertainment", "5.00"),
            self._new_plan(user_a, original_donor_day, "shopping", "100.00"),
            self._new_plan(user_a, next_month_day, "entertainment", "5.00"),
            self._new_plan(user_a, next_month_donor_day, "shopping", "100.00"),
        ]
        db_session.add_all(plans)
        db_session.commit()
        baseline = self._allocation_snapshot(db_session, user_a)

        txn_id = _create_txn(
            as_user_a,
            amount="30.00",
            category="food",
            spent_at=datetime(
                original_day.year,
                original_day.month,
                original_day.day,
                12,
                tzinfo=timezone.utc,
            ),
        )
        assert self._plan_values(db_session, user_a, original_day, "food") == (
            Decimal("30.00"),
            Decimal("30.00"),
            Decimal("30.00"),
        )
        assert self._plan_values(db_session, user_a, original_donor_day, "shopping")[
            :2
        ] == (Decimal("80.00"), Decimal("80.00"))

        response = as_user_a.put(f"/api/transactions/{txn_id}", json={"amount": 15.00})
        assert response.status_code == 200, response.text
        assert self._plan_values(db_session, user_a, original_day, "food") == (
            Decimal("15.00"),
            Decimal("15.00"),
            Decimal("15.00"),
        )
        assert self._plan_values(db_session, user_a, original_donor_day, "shopping")[
            :2
        ] == (Decimal("95.00"), Decimal("95.00"))

        response = as_user_a.put(
            f"/api/transactions/{txn_id}", json={"category": "entertainment"}
        )
        assert response.status_code == 200, response.text
        assert self._plan_values(db_session, user_a, original_day, "food") == (
            Decimal("10.00"),
            Decimal("10.00"),
            Decimal("0.00"),
        )
        assert self._plan_values(db_session, user_a, original_day, "entertainment") == (
            Decimal("15.00"),
            Decimal("15.00"),
            Decimal("15.00"),
        )
        assert self._plan_values(db_session, user_a, original_donor_day, "shopping")[
            :2
        ] == (Decimal("90.00"), Decimal("90.00"))

        response = as_user_a.put(
            f"/api/transactions/{txn_id}",
            json={
                "spent_at": datetime(
                    previous_day.year,
                    previous_day.month,
                    previous_day.day,
                    12,
                    tzinfo=timezone.utc,
                ).isoformat()
            },
        )
        assert response.status_code == 200, response.text
        assert self._plan_values(db_session, user_a, original_day, "entertainment") == (
            Decimal("5.00"),
            Decimal("5.00"),
            Decimal("0.00"),
        )
        assert self._plan_values(db_session, user_a, previous_day, "entertainment") == (
            Decimal("15.00"),
            Decimal("15.00"),
            Decimal("15.00"),
        )

        response = as_user_a.put(
            f"/api/transactions/{txn_id}",
            json={
                "spent_at": datetime(
                    next_month_day.year,
                    next_month_day.month,
                    next_month_day.day,
                    12,
                    tzinfo=timezone.utc,
                ).isoformat()
            },
        )
        assert response.status_code == 200, response.text
        assert self._plan_values(db_session, user_a, previous_day, "entertainment") == (
            Decimal("5.00"),
            Decimal("5.00"),
            Decimal("0.00"),
        )
        assert self._plan_values(db_session, user_a, original_donor_day, "shopping")[
            :2
        ] == (Decimal("100.00"), Decimal("100.00"))
        assert self._plan_values(
            db_session, user_a, next_month_day, "entertainment"
        ) == (Decimal("15.00"), Decimal("15.00"), Decimal("15.00"))
        assert self._plan_values(db_session, user_a, next_month_donor_day, "shopping")[
            :2
        ] == (Decimal("90.00"), Decimal("90.00"))

        response = as_user_a.delete(f"/api/transactions/{txn_id}")
        assert response.status_code == 200, response.text
        assert self._allocation_snapshot(db_session, user_a) == baseline

    def test_month_rebuild_replays_shared_donor_and_preserves_metadata(
        self, as_user_a, db_session, user_a
    ):
        transaction_month = self._previous_month(datetime.now(timezone.utc).date())
        first_day = transaction_month.replace(day=10)
        second_day = transaction_month.replace(day=11)
        donor_day = transaction_month.replace(day=20)
        donor = self._new_plan(user_a, donor_day, "shopping", "100.00")
        donor.plan_json = {
            "category_budgets": {"shopping": 100},
            "custom": "preserve-me",
        }
        db_session.add_all(
            [
                self._new_plan(user_a, first_day, "food", "0.00"),
                self._new_plan(user_a, second_day, "entertainment", "0.00"),
                donor,
            ]
        )
        db_session.commit()
        baseline = self._allocation_snapshot(db_session, user_a)

        first_id = _create_txn(
            as_user_a,
            amount="80.00",
            category="food",
            spent_at=datetime(
                first_day.year,
                first_day.month,
                first_day.day,
                12,
                tzinfo=timezone.utc,
            ),
        )
        assert (
            db_session.query(RedistributionEvent)
            .filter(RedistributionEvent.user_id == user_a.id)
            .count()
            == 1
        )
        second_id = _create_txn(
            as_user_a,
            amount="80.00",
            category="entertainment",
            spent_at=datetime(
                second_day.year,
                second_day.month,
                second_day.day,
                12,
                tzinfo=timezone.utc,
            ),
        )

        events = (
            db_session.query(RedistributionEvent)
            .filter(RedistributionEvent.user_id == user_a.id)
            .all()
        )
        assert len(events) == 2
        assert sorted(
            (event.to_category, Decimal(event.amount)) for event in events
        ) == [
            ("entertainment", Decimal("25.00")),
            ("food", Decimal("50.00")),
        ]

        snapshot = self._allocation_snapshot(db_session, user_a)
        assert sum(values[0] for values in snapshot.values()) == Decimal("100.00")
        assert self._plan_values(db_session, user_a, first_day, "food")[:2] == (
            Decimal("50.00"),
            Decimal("50.00"),
        )
        assert self._plan_values(db_session, user_a, second_day, "entertainment")[
            :2
        ] == (Decimal("25.00"), Decimal("25.00"))
        assert self._plan_values(db_session, user_a, donor_day, "shopping")[:2] == (
            Decimal("25.00"),
            Decimal("25.00"),
        )

        response = as_user_a.put(
            f"/api/transactions/{second_id}",
            json={"description": "metadata-only edit"},
        )
        assert response.status_code == 200, response.text
        assert (
            db_session.query(RedistributionEvent)
            .filter(RedistributionEvent.user_id == user_a.id)
            .count()
            == 2
        )

        response = as_user_a.delete(f"/api/transactions/{first_id}")
        assert response.status_code == 200, response.text
        assert (
            db_session.query(RedistributionEvent)
            .filter(RedistributionEvent.user_id == user_a.id)
            .count()
            == 2
        )
        assert self._plan_values(db_session, user_a, second_day, "entertainment")[
            :2
        ] == (Decimal("50.00"), Decimal("50.00"))
        assert self._plan_values(db_session, user_a, donor_day, "shopping")[:2] == (
            Decimal("50.00"),
            Decimal("50.00"),
        )

        response = as_user_a.delete(f"/api/transactions/{second_id}")
        assert response.status_code == 200, response.text
        assert self._allocation_snapshot(db_session, user_a) == baseline
        assert (
            db_session.query(RedistributionEvent)
            .filter(RedistributionEvent.user_id == user_a.id)
            .count()
            == 2
        )

        db_session.expire_all()
        stored_donor = (
            db_session.query(DailyPlan).filter(DailyPlan.id == donor.id).one()
        )
        assert stored_donor.plan_json == {
            "category_budgets": {"shopping": 100},
            "custom": "preserve-me",
        }

    def test_month_rebuild_does_not_lock_transaction_rows(self, db_session, user_a):
        """A ledger rebuild must not wait on unrelated transaction row locks."""
        transaction_month = self._previous_month(datetime.now(timezone.utc).date())
        transaction_day = transaction_month.replace(day=10)
        plan = self._new_plan(user_a, transaction_day, "food", "100.00")
        txn = Transaction(
            user_id=user_a.id,
            category="food",
            amount=Decimal("10.00"),
            spent_at=datetime(
                transaction_day.year,
                transaction_day.month,
                transaction_day.day,
                12,
                tzinfo=timezone.utc,
            ),
        )
        db_session.add_all([plan, txn])
        db_session.commit()

        SessionFactory = sessionmaker(
            bind=db_session.get_bind(),
            expire_on_commit=False,
            autoflush=False,
        )
        blocker = SessionFactory()
        rebuilder = SessionFactory()
        try:
            (
                blocker.query(Transaction)
                .filter(Transaction.id == txn.id)
                .with_for_update()
                .one()
            )
            rebuilder.execute(text("SET LOCAL lock_timeout = '500ms'"))

            rebuild_month_plan(
                rebuilder,
                user_a.id,
                transaction_day,
                tz="UTC",
                commit=False,
            )
        finally:
            rebuilder.rollback()
            blocker.rollback()
            rebuilder.close()
            blocker.close()

    def test_same_user_updates_lock_before_mutation_and_serialize(
        self, db_session, user_a, monkeypatch
    ):
        """Concurrent edits block before row mutation and finish without deadlock."""
        transaction_month = self._previous_month(datetime.now(timezone.utc).date())
        transaction_day = transaction_month.replace(day=10)
        plan = self._new_plan(user_a, transaction_day, "food", "100.00")
        transactions = [
            Transaction(
                user_id=user_a.id,
                category="food",
                amount=Decimal(amount),
                spent_at=datetime(
                    transaction_day.year,
                    transaction_day.month,
                    transaction_day.day,
                    12,
                    tzinfo=timezone.utc,
                ),
            )
            for amount in ("10.00", "20.00")
        ]
        db_session.add_all([plan, *transactions])
        db_session.commit()
        transaction_ids = [txn.id for txn in transactions]

        SessionFactory = sessionmaker(
            bind=db_session.get_bind(),
            expire_on_commit=False,
            autoflush=False,
        )
        gate = SessionFactory()
        entered_lock = Queue()
        real_lock = lock_user_ledger

        def signaled_lock(session, user_id):
            entered_lock.put(user_id)
            real_lock(session, user_id)

        monkeypatch.setattr(
            "app.api.transactions.services.lock_user_ledger",
            signaled_lock,
        )

        user_context = SimpleNamespace(id=user_a.id, timezone="UTC")

        def update_in_session(transaction_id, amount):
            from app.api.transactions.services import update_transaction

            session = SessionFactory()
            try:
                session.execute(text("SET LOCAL statement_timeout = '8s'"))
                return update_transaction(
                    user_context,
                    transaction_id,
                    SimpleNamespace(amount=Decimal(amount)),
                    session,
                )
            finally:
                session.close()

        futures = []
        executor = ThreadPoolExecutor(max_workers=2)
        lock_user_ledger(gate, user_a.id)
        try:
            futures = [
                executor.submit(
                    update_in_session,
                    transaction_ids[0],
                    "15.00",
                ),
                executor.submit(
                    update_in_session,
                    transaction_ids[1],
                    "25.00",
                ),
            ]
            entered_lock.get(timeout=3)
            entered_lock.get(timeout=3)

            # Both workers have reached the advisory lock. Their transaction
            # rows must still be untouched/unlocked because the lock is taken
            # before the initial query and flush.
            probe = SessionFactory()
            try:
                locked = (
                    probe.query(Transaction)
                    .filter(Transaction.id.in_(transaction_ids))
                    .with_for_update(nowait=True)
                    .all()
                )
                assert {txn.id for txn in locked} == set(transaction_ids)
            finally:
                probe.rollback()
                probe.close()
        finally:
            gate.commit()
            gate.close()

        try:
            assert all(future.result(timeout=10) is not None for future in futures)
        finally:
            executor.shutdown(wait=True, cancel_futures=True)

        db_session.expire_all()
        stored_amounts = {
            txn.id: Decimal(txn.amount)
            for txn in db_session.query(Transaction)
            .filter(Transaction.id.in_(transaction_ids))
            .all()
        }
        assert stored_amounts == {
            transaction_ids[0]: Decimal("15.00"),
            transaction_ids[1]: Decimal("25.00"),
        }
        assert self._plan_values(
            db_session,
            user_a,
            transaction_day,
            "food",
        )[
            2
        ] == Decimal("40.00")

    def test_month_rebuild_plan_reads_do_not_scale_with_bucket_count(
        self, db_session, user_a
    ):
        """The rebuild must not re-read the month once per (day, category).

        rebuild_month_plan already loads every plan row in the month FOR
        UPDATE under the advisory lock. Before the month rows were handed to
        the rebalancer, each overspent bucket issued its own entry lookup,
        future-entries scan and credit-back lookup — 169 daily_plan SELECTs
        for a realistic month, growing with the number of buckets.
        """
        from sqlalchemy import event

        month = self._previous_month(datetime.now(timezone.utc).date())
        categories = ["food", "entertainment", "shopping", "utilities"]

        db_session.add_all(
            [
                self._new_plan(user_a, month.replace(day=day), category, "25.00")
                for day in range(1, 21)
                for category in categories
            ]
        )
        db_session.add_all(
            [
                Transaction(
                    user_id=user_a.id,
                    category=category,
                    amount=Decimal("30.00"),
                    spent_at=datetime(
                        month.year, month.month, day, 12, tzinfo=timezone.utc
                    ),
                )
                for day in range(1, 21)
                for category in categories
            ]
        )
        db_session.commit()

        buckets = 20 * len(categories)
        plan_selects = []

        def _count(conn, cursor, statement, params, context, executemany):
            normalized = " ".join(statement.split()).upper()
            if normalized.startswith("SELECT") and "DAILY_PLAN" in normalized:
                plan_selects.append(normalized)

        bind = db_session.get_bind()
        event.listen(bind, "before_cursor_execute", _count)
        try:
            rebuild_month_plan(
                db_session, user_a.id, month, tz=user_a.timezone, commit=True
            )
        finally:
            event.remove(bind, "before_cursor_execute", _count)

        # One FOR UPDATE load of the month is enough. Allow a small constant
        # for session bookkeeping, but never anything proportional to buckets.
        assert buckets == 80
        assert len(plan_selects) <= 5, (
            f"{len(plan_selects)} daily_plan SELECTs for {buckets} buckets - "
            "the per-bucket re-read has come back"
        )

    def test_create_edit_delete_exact_values(self, as_user_a, db_session, user_a):
        base_balance, base_spent = _dashboard_numbers(as_user_a)

        # CREATE +42.00 (INV-12)
        txn_id = _create_txn(as_user_a, amount="42.00")
        balance, spent = _dashboard_numbers(as_user_a)
        assert balance == pytest.approx(base_balance - 42.00)
        assert spent == pytest.approx(base_spent + 42.00)

        plan_spent = self._plan_spent(db_session, user_a)
        assert plan_spent == Decimal("42.00")

        # EDIT 42 -> 100 (INV-13: delta applied once, not doubled to 142)
        resp = as_user_a.put(f"/api/transactions/{txn_id}", json={"amount": 100.00})
        assert resp.status_code == 200, resp.text
        balance, spent = _dashboard_numbers(as_user_a)
        assert balance == pytest.approx(base_balance - 100.00)
        assert spent == pytest.approx(base_spent + 100.00)

        plan_spent = self._plan_spent(db_session, user_a)
        assert plan_spent == Decimal(
            "100.00"
        ), f"daily-plan accrual is {plan_spent}; additive re-apply would give 142.00"

        # DELETE (INV-14 + V1: everything returns to the pre-txn values)
        resp = as_user_a.delete(f"/api/transactions/{txn_id}")
        assert resp.status_code == 200, resp.text
        balance, spent = _dashboard_numbers(as_user_a)
        assert balance == pytest.approx(base_balance)
        assert spent == pytest.approx(base_spent)

        plan_spent = self._plan_spent(db_session, user_a)
        assert plan_spent == Decimal("0.00")

    def test_category_change_moves_accrual(self, as_user_a, db_session, user_a):
        txn_id = _create_txn(as_user_a, amount="42.00", category="food")
        resp = as_user_a.put(
            f"/api/transactions/{txn_id}", json={"category": "entertainment"}
        )
        assert resp.status_code == 200, resp.text

        db_session.expire_all()
        assert self._plan_spent(db_session, user_a, "food") == Decimal("0.00")
        assert self._plan_spent(db_session, user_a, "entertainment") == Decimal("42.00")

    @staticmethod
    def _plan_spent(db_session, user, category="food"):
        from app.core.date_utils import day_to_range

        db_session.expire_all()
        day_start, day_end = day_to_range(datetime.now(timezone.utc).date())
        plan = (
            db_session.query(DailyPlan)
            .filter(
                DailyPlan.user_id == user.id,
                DailyPlan.date >= day_start,
                DailyPlan.date <= day_end,
                DailyPlan.category == category,
            )
            .first()
        )
        return (
            Decimal(plan.spent_amount or 0).quantize(Decimal("0.01"))
            if plan
            else Decimal("0.00")
        )

    @staticmethod
    def _previous_month(day):
        if day.month == 1:
            return day.replace(year=day.year - 1, month=12, day=1)
        return day.replace(month=day.month - 1, day=1)

    @staticmethod
    def _new_plan(user, day, category, planned):
        amount = Decimal(planned)
        return DailyPlan(
            user_id=user.id,
            date=datetime(day.year, day.month, day.day, 12, tzinfo=timezone.utc),
            category=category,
            planned_amount=amount,
            daily_budget=amount,
            spent_amount=Decimal("0.00"),
        )

    @staticmethod
    def _plan_values(db_session, user, day, category):
        from app.core.date_utils import day_to_range

        db_session.expire_all()
        day_start, day_end = day_to_range(day)
        plan = (
            db_session.query(DailyPlan)
            .filter(
                DailyPlan.user_id == user.id,
                DailyPlan.date >= day_start,
                DailyPlan.date <= day_end,
                DailyPlan.category == category,
            )
            .one()
        )
        return tuple(
            Decimal(value or 0).quantize(Decimal("0.01"))
            for value in (
                plan.planned_amount,
                plan.daily_budget,
                plan.spent_amount,
            )
        )

    @staticmethod
    def _allocation_snapshot(db_session, user):
        db_session.expire_all()
        rows = (
            db_session.query(DailyPlan)
            .filter(DailyPlan.user_id == user.id)
            .order_by(DailyPlan.date, DailyPlan.category)
            .all()
        )
        return {
            (
                row.date.date() if hasattr(row.date, "date") else row.date,
                row.category,
            ): tuple(
                Decimal(value or 0).quantize(Decimal("0.01"))
                for value in (
                    row.planned_amount,
                    row.daily_budget,
                    row.spent_amount,
                )
            )
            for row in rows
        }


class TestOwnershipIsolation:
    """User B must never read or mutate user A's transactions."""

    def test_cross_user_access_denied(self, client, db_session, user_a, user_b):
        from app.main import app

        _auth_as(user_a)
        try:
            txn_id = _create_txn(client)

            _auth_as(user_b)
            assert client.get(f"/api/transactions/{txn_id}").status_code == 404
            assert (
                client.put(
                    f"/api/transactions/{txn_id}", json={"amount": 1.00}
                ).status_code
                == 404
            )
            assert client.delete(f"/api/transactions/{txn_id}").status_code == 404

            resp = client.get("/api/transactions/")
            assert resp.status_code == 200
            listed = resp.json()["data"]
            if isinstance(listed, dict):
                listed = listed.get("transactions", listed)
            assert not any(str(t["id"]) == txn_id for t in listed)

            # A's transaction is untouched
            db_session.expire_all()
            stored = db_session.get(Transaction, txn_id)
            assert stored.deleted_at is None
            assert stored.amount == Decimal("42.00")
        finally:
            app.dependency_overrides.pop(
                __import__(
                    "app.api.dependencies", fromlist=["get_current_user"]
                ).get_current_user,
                None,
            )

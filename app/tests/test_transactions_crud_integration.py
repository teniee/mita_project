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

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db.models import DailyPlan, Transaction, User


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


def _create_txn(client, amount="42.00", category="food"):
    resp = client.post(
        "/api/transactions/",
        json={
            "amount": float(amount),
            "category": category,
            "description": "integration txn",
            "spent_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert resp.status_code in (200, 201), resp.text
    body = resp.json()
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

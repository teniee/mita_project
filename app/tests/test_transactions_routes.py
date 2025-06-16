import datetime
import json
from types import SimpleNamespace
from decimal import Decimal
import pytest

from app.api.transactions.routes import create_transaction
from app.api.transactions.schemas import TxnIn

class DummyDB:
    def __init__(self):
        self.added = []
        self.committed = False
        self.refreshed = []
    def add(self, obj):
        self.added.append(obj)
    def commit(self):
        self.committed = True
    def refresh(self, obj):
        self.refreshed.append(obj)

class DummyTxn:
    def __init__(self, **kw):
        self.id = "t123"
        for k, v in kw.items():
            setattr(self, k, v)

class DummyPlan:
    def __init__(self):
        self.spent_amount = Decimal("0.0")

@pytest.mark.asyncio
async def test_create_transaction_updates_plan(monkeypatch):
    plan = DummyPlan()

    def dummy_apply(db, txn):
        plan.spent_amount += txn.amount

    monkeypatch.setattr("app.api.transactions.services.Transaction", DummyTxn)
    monkeypatch.setattr(
        "app.api.transactions.services.apply_transaction_to_plan", dummy_apply
    )
    monkeypatch.setattr(
        "app.api.transactions.routes.success_response", lambda data=None, message="": data
    )

    db = DummyDB()
    user = SimpleNamespace(id="u1")
    data = TxnIn(
        category="food",
        amount=12.5,
        currency="USD",
        spent_at=datetime.datetime(2025, 1, 1),
    )

    await create_transaction(data, user=user, db=db)

    assert plan.spent_amount == Decimal("12.5")
    assert db.committed

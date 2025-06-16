import datetime
from types import SimpleNamespace
from decimal import Decimal

from app.api.transactions.services import add_transaction


class DummyDB:
    def __init__(self):
        self.committed = False
        self.added = []
        self.refreshed = []

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.committed = True

    def refresh(self, obj):
        self.refreshed.append(obj)


class DummyTxn:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def test_add_transaction_records_expense(monkeypatch):
    monkeypatch.setattr("app.api.transactions.services.Transaction", DummyTxn)
    spent = {"amount": Decimal("0")}

    def fake_apply(db, txn):
        spent["amount"] += txn.amount

    monkeypatch.setattr(
        "app.api.transactions.services.apply_transaction_to_plan",
        fake_apply,
    )

    db = DummyDB()
    data = SimpleNamespace(
        category="food",
        amount=12.5,
        currency="USD",
        spent_at=datetime.datetime(2025, 1, 1),
    )

    add_transaction("u1", data, db)

    # Daily plan should be updated once with the transaction amount
    assert spent["amount"] == Decimal("12.5")
    assert db.committed

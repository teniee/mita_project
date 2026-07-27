import datetime
from decimal import Decimal
from types import SimpleNamespace

from app.api.transactions.services import add_transaction


class DummyDB:
    def __init__(self):
        self.committed = False
        self.flushed = False
        self.added = []
        self.refreshed = []

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.committed = True

    def flush(self):
        self.flushed = True

    def rollback(self):
        self.committed = False

    def refresh(self, obj):
        self.refreshed.append(obj)


class DummyTxn:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def test_add_transaction_records_expense(monkeypatch):
    monkeypatch.setattr("app.api.transactions.services.Transaction", DummyTxn)
    spent = {"amount": Decimal("0")}

    def fake_commit(db, txn, *, run_side_effects=True):
        spent["amount"] += txn.amount
        return None

    monkeypatch.setattr(
        "app.api.transactions.services.commit_transaction_to_ledger",
        fake_commit,
    )

    db = DummyDB()
    data = SimpleNamespace(
        category="food",
        amount=12.5,
        spent_at=datetime.datetime(2025, 1, 1),
    )

    user = SimpleNamespace(id="u1", timezone="UTC")
    add_transaction(user, data, db)

    # Daily plan should be updated once with the transaction amount.
    # add_transaction hands the whole ledger mutation to the canonical
    # service, so the flush/commit assertions moved there with it.
    assert spent["amount"] == Decimal("12.5")

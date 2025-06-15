import datetime
import importlib
import sys
from types import SimpleNamespace

if isinstance(sys.modules.get("app.db.models"), object) and not hasattr(
    sys.modules.get("app.db.models"), "Transaction"
):
    # restore real models module if previous tests replaced it
    sys.modules.pop("app.db.models", None)
    importlib.import_module("app.db.models")

from app.api.transactions.services import add_transaction


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
        self.__dict__.update(kw)


def test_add_transaction_triggers_plan(monkeypatch):
    created = {}

    def dummy_txn(**kw):
        t = DummyTxn(**kw)
        created["txn"] = t
        return t

    monkeypatch.setattr("app.api.transactions.services.Transaction", dummy_txn)

    called = {}

    def dummy_apply(db, txn):
        called["args"] = (db, txn)

    monkeypatch.setattr(
        "app.api.transactions.services.apply_transaction_to_plan", dummy_apply
    )

    db = DummyDB()
    data = SimpleNamespace(
        category="food",
        amount=12.5,
        currency="USD",
        spent_at=datetime.datetime(2025, 1, 1),
    )

    result = add_transaction("u1", data, db)

    assert result is created["txn"]
    assert called["args"] == (db, created["txn"])
    assert db.committed

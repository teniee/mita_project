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

from app.api.transactions.services import add_transaction, list_user_transactions


class DummyDB:
    def __init__(self):
        self.added = []
        self.committed = False
        self.flushed = False
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


def test_add_transaction_triggers_plan(monkeypatch):
    created = {}

    def dummy_txn(**kw):
        t = DummyTxn(**kw)
        created["txn"] = t
        return t

    monkeypatch.setattr("app.api.transactions.services.Transaction", dummy_txn)

    called = {}

    # add_transaction now delegates the whole lock/insert/rebuild/commit
    # sequence to the one ledger service, so that is what we intercept.
    def dummy_commit(db, txn, *, run_side_effects=True):
        called["args"] = (db, txn)
        return None

    monkeypatch.setattr(
        "app.api.transactions.services.commit_transaction_to_ledger", dummy_commit
    )

    db = DummyDB()
    data = SimpleNamespace(
        category="food",
        amount=12.5,
        spent_at=datetime.datetime(2025, 1, 1),
    )

    user = SimpleNamespace(id="u1", timezone="UTC")
    result = add_transaction(user, data, db)

    assert result.transaction is created["txn"]
    assert result.rebalance_plan is None
    assert called["args"] == (db, created["txn"])
    # The flush/commit pair now belongs to commit_transaction_to_ledger,
    # which is stubbed here and exercised for real against PostgreSQL in
    # app/tests/test_ledger_entry_paths.py and the CRUD integration suite.


def test_list_user_transactions_pagination(monkeypatch):
    user = SimpleNamespace(id="u1", timezone="UTC")

    txns = [
        SimpleNamespace(
            id=str(i),
            user_id="u1",
            category="food",
            spent_at=datetime.datetime(2025, 1, i + 1),
        )
        for i in range(5)
    ]

    class DummyQuery:
        def __init__(self, items):
            self.items = items

        def filter(self, *args, **kwargs):
            return self

        def order_by(self, *args, **kwargs):
            self.items.sort(key=lambda t: t.spent_at, reverse=True)
            return self

        def offset(self, skip):
            self.items = self.items[skip:]
            return self

        def limit(self, limit):
            self.items = self.items[:limit]
            return self

        def all(self):
            return list(self.items)

    class DummyDB:
        def query(self, model):
            return DummyQuery(list(txns))

    monkeypatch.setattr(
        "app.api.transactions.services.from_user_timezone", lambda dt, tz: dt
    )
    monkeypatch.setattr(
        "app.api.transactions.services.to_user_timezone", lambda dt, tz: dt
    )

    result = list_user_transactions(user, DummyDB(), skip=1, limit=2)

    assert [t.id for t in result] == ["3", "2"]

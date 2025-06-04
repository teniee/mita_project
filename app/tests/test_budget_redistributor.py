from datetime import date
import sys
from types import SimpleNamespace

class DummyField:
    def __ge__(self, other):
        return self

    def __lt__(self, other):
        return self

    def __eq__(self, other):
        return self


DummyModel = SimpleNamespace(
    user_id=DummyField(),
    date=DummyField(),
    category=DummyField(),
    planned_amount=DummyField(),
    spent_amount=DummyField(),
)
sys.modules['app.db.models'] = SimpleNamespace(DailyPlan=DummyModel)
from app.services.budget_redistributor import redistribute_budget_for_user


class DummyEntry:
    def __init__(self, user_id, category, day, planned, spent):
        self.user_id = user_id
        self.category = category
        self.date = day
        self.planned_amount = planned
        self.spent_amount = spent


class DummyQuery:
    def __init__(self, entries):
        self.entries = entries

    def filter(self, *args, **kwargs):
        return self

    def all(self):
        return self.entries


class DummyDB:
    def __init__(self, entries):
        self._entries = entries
        self.committed = False

    def query(self, model):
        return DummyQuery(self._entries)

    def commit(self):
        self.committed = True


def test_redistribute_sums_transfers():
    entries = [
        DummyEntry(1, "rent", date(2023, 1, 1), 100.0, 150.0),
        DummyEntry(1, "rent", date(2023, 1, 2), 100.0, 150.0),
        DummyEntry(1, "groceries", date(2023, 1, 3), 100.0, 50.0),
        DummyEntry(1, "entertainment", date(2023, 1, 4), 60.0, 30.0),
    ]
    db = DummyDB(entries)

    redistribute_budget_for_user(db, user_id=1, year=2023, month=1)

    assert db.committed
    # Total surplus = 80, should be added to first rent entry
    assert entries[0].planned_amount == 180.0

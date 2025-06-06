from decimal import Decimal
from types import SimpleNamespace

from app.services.category_goal_service import get_goal_progress, set_category_goal


class DummyQuery:
    def __init__(self, db, model):
        self.db = db
        self.model = model
        self.filters = {}

    def filter_by(self, **kwargs):
        self.filters.update(kwargs)
        return self

    def first(self):
        for obj in self.db[self.model.__name__]:
            if all(getattr(obj, k) == v for k, v in self.filters.items()):
                return obj
        return None

    def all(self):
        return [
            obj
            for obj in self.db[self.model.__name__]
            if all(getattr(obj, k) == v for k, v in self.filters.items())
        ]

    def scalar(self):
        return sum(
            tx.amount
            for tx in self.db["Transaction"]
            if all(
                [
                    tx.user_id == self.filters.get("user_id", tx.user_id),
                ]
            )
        )

    def filter(self, *args, **kwargs):
        return self


class DummyDB:
    def __init__(self):
        self.storage = {
            "CategoryGoal": [],
            "Transaction": [],
        }
        self.committed = False

    def query(self, model):
        return DummyQuery(self.storage, model)

    def add(self, obj):
        self.storage[obj.__class__.__name__].append(obj)

    def commit(self):
        self.committed = True

    def refresh(self, obj):
        pass


def test_set_and_progress():
    db = DummyDB()
    goal = set_category_goal(db, "u1", "food", 2025, 5, 100.0)
    assert goal.category == "food"
    assert db.committed

    # add a transaction
    Tx = SimpleNamespace(
        user_id="u1", category="food", amount=Decimal("40"), spent_at=None
    )
    db.storage["Transaction"].append(Tx)

    progress = get_goal_progress(db, "u1", "food", 2025, 5)
    assert progress["spent"] == 40.0
    assert progress["remaining"] == 60.0

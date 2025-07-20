from app.services.core.engine.budget_tracker import BudgetTracker


class DummySession:
    def query(self, *args, **kwargs):
        return self

    def filter_by(self, *args, **kwargs):
        return self

    def filter(self, *args, **kwargs):
        return self

    def all(self):
        return []


def test_tracker_basic_usage():
    tracker = BudgetTracker(DummySession(), user_id=1, year=2025, month=5)
    assert tracker is not None

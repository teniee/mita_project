from app.services.core.engine.budget_auto_adapter import adapt_category_weights


class DummySnapshot:
    def __init__(self, risk, tags):
        self.risk = risk
        self.full_profile = {"behavior_tags": tags}


class DummyDB:
    def query(self, model):
        return self

    def filter_by(self, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def first(self):
        return DummySnapshot("high", ["emotional_spender", "food_dominated"])


def test_adapt_category_weights():
    default = {
        "shopping": 0.2,
        "restaurants": 0.2,
        "groceries": 0.2,
        "entertainment": 0.2,
        "savings": 0.2,
    }
    db = DummyDB()
    adapted = adapt_category_weights(user_id=1, default_weights=default, db=db)
    assert isinstance(adapted, dict)
    assert abs(sum(adapted.values()) - 1.0) < 0.01

from app.services.advisory_service import AdvisoryService


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


def test_evaluate_user_risk_records_advice(monkeypatch):
    db = DummyDB()

    def fake_eval(user_id):
        return {"risk_level": "high", "reason": "bad"}

    monkeypatch.setattr(
        "app.engine.risk_predictor.evaluate_user_risk",
        fake_eval,
    )
    service = AdvisoryService(db)

    result = service.evaluate_user_risk("u1")

    assert result["risk_level"] == "high"
    assert db.committed
    assert db.added and db.added[0].type == "risk"


def test_installment_advice_saved_on_fail(monkeypatch):
    db = DummyDB()

    def fake_eval(user_id, price, months):
        return {"can_afford": False, "monthly_payment": 10, "reason": "no"}

    monkeypatch.setattr(
        (
            "app.engine.financial.installment_evaluator."
            "can_user_afford_"
            "installment"
        ),
        fake_eval,
    )
    service = AdvisoryService(db)

    result = service.can_user_afford_installment("u1", 100, 10)

    assert not result["can_afford"]
    assert db.committed
    assert db.added and db.added[0].type == "installment"

from types import SimpleNamespace

from app.api.financial.services import evaluate_installment


class DummyDB:
    def __init__(self, token=True):
        self.added = []
        self.committed = False
        self.refreshed = []
        self.token_record = SimpleNamespace(token="tok") if token else None

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.committed = True

    def refresh(self, obj):
        self.refreshed.append(obj)

    # query helpers for PushToken
    def query(self, model):
        self.q_model = model
        return self

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def first(self):
        return self.token_record


def test_evaluate_installment_pushes_on_fail(monkeypatch):
    db = DummyDB()

    class DummyAdvisory:
        def __init__(self, _db):
            self.db = _db

        def can_user_afford_installment(self, user_id, price, months):
            self.db.commit()
            return {"can_afford": False, "monthly_payment": 10, "reason": "no"}

    sent = {}
    monkeypatch.setattr(
        "app.api.financial.services.AdvisoryService",
        lambda db: DummyAdvisory(db),
    )
    monkeypatch.setattr(
        "app.api.financial.services.send_push_notification",
        lambda **kw: sent.setdefault("msg", kw),
    )

    result = evaluate_installment("u1", 100, 10, db)

    assert not result["can_afford"]
    assert db.committed
    assert sent["msg"]["user_id"] == "u1"


def test_evaluate_installment_no_push_when_safe(monkeypatch):
    db = DummyDB()

    class DummyAdvisory:
        def __init__(self, _db):
            pass

        def can_user_afford_installment(self, user_id, price, months):
            return {"can_afford": True, "monthly_payment": 10, "reason": "ok"}

    monkeypatch.setattr(
        "app.api.financial.services.AdvisoryService",
        lambda db: DummyAdvisory(db),
    )
    monkeypatch.setattr(
        "app.api.financial.services.send_push_notification",
        lambda **kw: (_ for _ in ()).throw(Exception("should not send")),
    )

    result = evaluate_installment("u1", 100, 10, db)

    assert result["can_afford"]
    assert not db.committed

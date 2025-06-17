from types import SimpleNamespace

from app.services.core.engine.cron_task_ai_advice import run_ai_advice_batch


class DummyQuery:
    def __init__(self, items):
        self.items = items

    def filter(self, *args, **kwargs):
        return self

    def filter_by(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        return self.items

    def first(self):
        return self.items[0] if self.items else None


class DummyDB:
    def __init__(self, users, tokens=None, advice=None):
        self.users = users
        self.tokens = tokens or {}
        self.advice = advice
        self.committed = False

    def query(self, model):
        name = model.__name__
        if name == "User":
            return DummyQuery(self.users)
        if name == "PushToken":
            token = self.tokens.get(self.users[0].id)
            return DummyQuery([SimpleNamespace(token=token)] if token else [])
        if name == "BudgetAdvice":
            return DummyQuery([self.advice] if self.advice else [])
        return DummyQuery([])

    def commit(self):
        self.committed = True


def test_run_ai_advice_batch_sends(monkeypatch):
    user = SimpleNamespace(id="u1", is_active=True)
    db = DummyDB([user], tokens={"u1": "tok"})

    def dummy_get_db():
        return iter([db])

    sent = {}

    class DummyService:
        def __init__(self, _db):
            pass

        def evaluate_user_risk(self, user_id):
            sent["evaluated"] = user_id
            return {"reason": "be careful"}

    monkeypatch.setattr(
        "app.services.core.engine.cron_task_ai_advice.get_db",
        dummy_get_db,
    )
    monkeypatch.setattr(
        "app.services.core.engine.cron_task_ai_advice.AdvisoryService",
        DummyService,
    )
    monkeypatch.setattr(
        "app.services.core.engine.cron_task_ai_advice.send_push_notification",
        lambda **kw: sent.setdefault("push", kw),
    )

    run_ai_advice_batch()

    assert sent["evaluated"] == "u1"
    assert sent["push"]["user_id"] == "u1"

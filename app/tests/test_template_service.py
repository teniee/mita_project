from app.services.template_service import AIAdviceTemplateService
from app.db.models.ai_advice_template import AIAdviceTemplate


class DummyQuery:
    def __init__(self, db):
        self.db = db
        self.key = None

    def filter(self, expr):
        self.key = getattr(expr, "right", None)
        if self.key is not None:
            self.key = getattr(self.key, "value", None)
        return self

    def first(self):
        return self.db.storage.get(self.key)

    def all(self):
        return list(self.db.storage.values())


class DummyDB:
    def __init__(self):
        self.storage = {}

    def query(self, model):
        return DummyQuery(self)

    def add(self, obj):
        self.storage[obj.key] = obj

    def commit(self):
        pass

    def refresh(self, obj):
        pass

    def delete(self, obj):
        self.storage.pop(obj.key, None)


def test_template_crud():
    db = DummyDB()

    service = AIAdviceTemplateService(db)
    service.set("test", "hello")
    assert service.get("test") == "hello"

    service.set("test", "world")
    assert service.get("test") == "world"

    assert len(service.list_all()) == 1

    service.delete("test")
    assert service.get("test") is None


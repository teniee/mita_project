import importlib
import sys

if isinstance(sys.modules.get("app.db.models"), object) and not hasattr(
    sys.modules.get("app.db.models"), "AIAnalysisSnapshot"
):
    sys.modules.pop("app.db.models", None)
    importlib.import_module("app.db.models")

from app.services.core.engine.ai_snapshot_service import save_ai_snapshot

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


def test_save_ai_snapshot(monkeypatch):
    class DummySnap:
        def __init__(self, **kw):
            self.__dict__.update(kw)
            self.id = "s1"

    monkeypatch.setattr(
        "app.services.core.engine.ai_snapshot_service.AIAnalysisSnapshot",
        DummySnap,
    )
    monkeypatch.setattr(
        "app.services.core.engine.ai_snapshot_service.build_user_profile",
        lambda **kw: {"user": kw.get("user_id")},
    )
    monkeypatch.setattr(
        "app.services.core.engine.ai_snapshot_service.generate_financial_rating",
        lambda profile: {"rating": "A", "risk": "low", "summary": "ok"},
    )

    db = DummyDB()
    result = save_ai_snapshot(1, db, 2025, 6)

    assert result["status"] == "saved"
    assert db.committed
    assert isinstance(db.added[0], DummySnap)

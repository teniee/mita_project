from types import SimpleNamespace

import app.services.task_manager as tm_mod
import app.core.task_queue as tq_mod
from app import legacy_tasks


def test_enqueue_jobs(monkeypatch):
    calls = []

    class DummyTaskManager:
        def submit_daily_advice_batch(self):
            calls.append("daily_advice_batch")
            return SimpleNamespace(task_id="t1")

        def submit_monthly_redistribution_batch(self):
            calls.append("monthly_redistribution_batch")
            return SimpleNamespace(task_id="t2")

    def dummy_enqueue_task(func, *args, **kwargs):
        calls.append(func.__name__)
        return SimpleNamespace(id="j1")

    monkeypatch.setattr(tm_mod, "task_manager", DummyTaskManager())
    monkeypatch.setattr(tq_mod, "enqueue_task", dummy_enqueue_task)

    legacy_tasks.enqueue_daily_advice()
    legacy_tasks.enqueue_monthly_redistribution()
    legacy_tasks.enqueue_subscription_refresh()

    assert calls == [
        "daily_advice_batch",
        "monthly_redistribution_batch",
        "refresh_premium_status",
    ]


from app import tasks


def test_enqueue_jobs(monkeypatch):
    calls = []

    class DummyQueue:
        def enqueue(self, func):
            calls.append(func.__name__)

    monkeypatch.setattr(tasks, "queue", DummyQueue())
    tasks.enqueue_daily_advice()
    tasks.enqueue_monthly_redistribution()
    tasks.enqueue_subscription_refresh()

    assert calls == [
        "run_ai_advice_batch",
        "run_budget_redistribution_batch",
        "refresh_premium_status",
    ]

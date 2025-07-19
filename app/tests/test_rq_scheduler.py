import importlib
import sys
import types


def test_monthly_redistribution_scheduled(monkeypatch):
    jobs = []

    class DummyScheduler:
        def __init__(self, queue_name=None, connection=None):
            pass

        def cancel_all(self):
            pass

        def cron(self, cron_string, func, repeat=None, queue_name=None):
            jobs.append((cron_string, func.__name__))

    dummy_rq = types.ModuleType("rq_scheduler")
    dummy_rq.Scheduler = DummyScheduler
    monkeypatch.setitem(sys.modules, "rq_scheduler", dummy_rq)

    dummy_redis = types.ModuleType("redis")
    dummy_redis.Redis = types.SimpleNamespace(from_url=lambda url: None)
    monkeypatch.setitem(sys.modules, "redis", dummy_redis)

    import scripts.rq_scheduler as rq

    importlib.reload(rq)

    assert ("0 1 1 * *", "enqueue_monthly_redistribution") in jobs

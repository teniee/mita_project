import importlib

import redis
import rq


def test_worker_initializes(monkeypatch):
    called = {}

    class DummyWorker:
        def __init__(self, queues):
            called["queues"] = queues

        def work(self):
            called["worked"] = True

    class DummyConnCtx:
        def __init__(self, conn):
            pass

        def __enter__(self):
            return None

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(redis.Redis, "from_url", lambda url: object())
    monkeypatch.setattr(rq, "Connection", DummyConnCtx)
    monkeypatch.setattr(rq, "Worker", DummyWorker)
    monkeypatch.setattr(rq, "Queue", lambda *a, **k: None)

    importlib.reload(importlib.import_module("app.worker"))
    assert called["queues"] == ["default"]
    assert called["worked"]

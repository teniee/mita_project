import os

import rq
from redis import Redis

try:
    from rq import Connection
except ImportError:  # RQ>=2.0 no longer exposes Connection at top level
    from rq.connections import Connection

    rq.Connection = Connection  # provide backward-compatible attribute

from rq import Queue, Worker

redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
conn = Redis.from_url(redis_url)

with Connection(conn):
    worker = Worker(["default"])
    worker.work()

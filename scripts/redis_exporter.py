import os
import time

from prometheus_client import Gauge, start_http_server
from redis import Redis
from rq import Queue


def collect_metrics(queue: Queue, redis: Redis):
    jobs = queue.get_jobs()
    LENGTH.set(len(jobs))
    if jobs:
        oldest = min((j.enqueued_at for j in jobs if j.enqueued_at), default=None)
        if oldest:
            latency = time.time() - oldest.timestamp()
            LATENCY.set(latency)
        else:
            LATENCY.set(0)
    else:
        LATENCY.set(0)
    info = redis.info()
    EVICTED.set(info.get("evicted_keys", 0))


if __name__ == "__main__":
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    queue_name = os.getenv("QUEUE_NAME", "default")
    port = int(os.getenv("METRICS_PORT", "8001"))

    redis = Redis.from_url(redis_url)
    queue = Queue(queue_name, connection=redis)

    LATENCY = Gauge("queue_latency_seconds", "Age of oldest job in the queue")
    LENGTH = Gauge("queue_length", "Number of jobs in the queue")
    EVICTED = Gauge("evicted_keys_total", "Total evicted keys from Redis")

    start_http_server(port)

    while True:
        collect_metrics(queue, redis)
        time.sleep(5)

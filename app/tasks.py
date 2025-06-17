import os
from redis import Redis
from rq import Queue

redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
queue = Queue("default", connection=Redis.from_url(redis_url))


def enqueue_daily_advice() -> None:
    from app.services.core.engine.cron_task_ai_advice import run_ai_advice_batch
    queue.enqueue(run_ai_advice_batch)


def enqueue_monthly_redistribution() -> None:
    from app.services.core.engine.cron_task_budget_redistribution import (
        run_budget_redistribution_batch,
    )
    queue.enqueue(run_budget_redistribution_batch)


def enqueue_subscription_refresh() -> None:
    from app.services.core.engine.cron_task_subscription_refresh import (
        refresh_premium_status,
    )
    queue.enqueue(refresh_premium_status)

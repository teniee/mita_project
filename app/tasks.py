"""
Legacy task enqueuing functions for backward compatibility.
Updated to use the new async task system.
"""

import os
from app.services.task_manager import task_manager


def enqueue_daily_advice() -> None:
    """Enqueue daily AI advice batch task using new async system."""
    task_info = task_manager.submit_daily_advice_batch()
    print(f"Daily advice batch enqueued: {task_info.task_id}")


def enqueue_monthly_redistribution() -> None:
    """Enqueue monthly redistribution batch task using new async system."""
    task_info = task_manager.submit_monthly_redistribution_batch()
    print(f"Monthly redistribution batch enqueued: {task_info.task_id}")


def enqueue_subscription_refresh() -> None:
    """Enqueue subscription refresh task using new async system."""
    from app.services.core.engine.cron_task_subscription_refresh import refresh_premium_status
    from app.core.task_queue import enqueue_task
    
    job = enqueue_task(refresh_premium_status)
    print(f"Subscription refresh enqueued: {job.id}")


def enqueue_daily_reminders() -> None:
    """Enqueue daily email reminders using legacy method (for now)."""
    # Note: This could be converted to use the new notification task system
    from app.services.core.engine.cron_task_reminders import run_daily_email_reminders
    from app.core.task_queue import enqueue_task
    
    job = enqueue_task(run_daily_email_reminders)
    print(f"Daily reminders enqueued: {job.id}")


# Legacy Redis queue for backward compatibility
from redis import Redis
from rq import Queue

redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
queue = Queue("default", connection=Redis.from_url(redis_url))

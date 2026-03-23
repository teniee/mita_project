"""
Legacy task enqueuing functions for backward compatibility.
Updated to use the new async task system.
"""

import logging
import os

logger = logging.getLogger(__name__)


def enqueue_daily_advice() -> None:
    """Enqueue daily AI advice batch task using new async system."""
    # Use delayed import to avoid circular dependency
    from app.services.task_manager import task_manager
    task_info = task_manager.submit_daily_advice_batch()
    logger.info("Daily advice batch enqueued: %s", task_info.task_id)


def enqueue_monthly_redistribution() -> None:
    """Enqueue monthly redistribution batch task using new async system."""
    # Use delayed import to avoid circular dependency
    from app.services.task_manager import task_manager
    task_info = task_manager.submit_monthly_redistribution_batch()
    logger.info("Monthly redistribution batch enqueued: %s", task_info.task_id)


def enqueue_subscription_refresh() -> None:
    """Enqueue subscription refresh task using new async system."""
    from app.services.core.engine.cron_task_subscription_refresh import refresh_premium_status
    from app.core.task_queue import enqueue_task
    
    job = enqueue_task(refresh_premium_status)
    logger.info("Subscription refresh enqueued: %s", job.id)


def enqueue_daily_reminders() -> None:
    """Enqueue daily email reminders using legacy method (for now)."""
    # Note: This could be converted to use the new notification task system
    from app.services.core.engine.cron_task_reminders import run_daily_email_reminders
    from app.core.task_queue import enqueue_task
    
    job = enqueue_task(run_daily_email_reminders)
    logger.info("Daily reminders enqueued: %s", job.id)


# Legacy Redis queue for backward compatibility - EMERGENCY FIX: Lazy initialization
def get_legacy_queue():
    """Get legacy Redis queue with lazy initialization to prevent startup hangs"""
    try:
        from redis import Redis
        from rq import Queue
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        if not redis_url or redis_url == "":
            # Fall back to in-memory task system
            return None
        return Queue("default", connection=Redis.from_url(redis_url))
    except Exception:
        # Fall back to in-memory task system
        return None

# Remove immediate Redis connection - use lazy loading
queue = None

import os

from redis import Redis
from rq_scheduler import Scheduler

from app.legacy_tasks import (
    enqueue_daily_advice,
    enqueue_daily_reminders,
    enqueue_monthly_redistribution,
    enqueue_subscription_refresh,
)
from app.services.core.engine.cron_task_streak_wins import run_streak_win_check
from app.services.core.engine.cron_task_followup_reminder import run_followup_reminders

redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
conn = Redis.from_url(redis_url)
scheduler = Scheduler(queue_name="default", connection=conn)

# Clear existing jobs on startup
scheduler.cancel_all()

# Run advisory push every hour and send at 08:00 user local time
scheduler.cron(
    "0 * * * *",
    func=enqueue_daily_advice,
    repeat=None,
    queue_name="default",
)

# Daily email reminders at 09:00 UTC
scheduler.cron(
    "0 9 * * *",
    func=enqueue_daily_reminders,
    repeat=None,
    queue_name="default",
)

# Monthly redistribution on the 1st at 01:00 UTC
scheduler.cron(
    "0 1 1 * *",
    func=enqueue_monthly_redistribution,
    repeat=None,
    queue_name="default",
)

# Subscription refresh every day at 02:00 UTC
scheduler.cron(
    "0 2 * * *",
    func=enqueue_subscription_refresh,
    repeat=None,
    queue_name="default",
)

# Streak win check every day at 08:00 UTC
scheduler.cron(
    "0 8 * * *",
    func=run_streak_win_check,
    repeat=None,
    queue_name="default",
)

# Follow-up reminders every day at 09:05 UTC (offset to avoid conflict with daily_reminders)
scheduler.cron(
    "5 9 * * *",
    func=run_followup_reminders,
    repeat=None,
    queue_name="default",
)

if __name__ == "__main__":
    scheduler.run()

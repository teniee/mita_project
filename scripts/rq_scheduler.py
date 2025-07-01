import os

from redis import Redis
from rq_scheduler import Scheduler

from app.tasks import (
    enqueue_daily_advice,
    enqueue_daily_reminders,
    enqueue_monthly_redistribution,
    enqueue_subscription_refresh,
)

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

if __name__ == "__main__":
    scheduler.run()

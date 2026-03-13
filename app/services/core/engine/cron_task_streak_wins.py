"""
Daily Streak Win Cron Task
Checks all active users for 7-day on-budget streaks and sends positive notifications.
Based on behavioral economics: celebrate small wins (Thaler).
"""
import logging
from datetime import date

from sqlalchemy.orm import Session

from app.core.session import get_db
from app.db.models import User
from app.services.win_notification_service import WinNotificationService

logger = logging.getLogger(__name__)


def run_streak_win_check() -> None:
    """
    Daily cron: check all active users for spending streaks.
    Send positive notification if 7-day green streak detected.
    """
    db: Session = next(get_db())
    today = date.today()
    notified = 0
    errors = 0

    users = db.query(User).filter(User.is_active.is_(True)).all()
    svc = WinNotificationService(db)

    for user in users:
        try:
            win = svc.check_streak_win(user_id=user.id, check_date=today)
            if win:
                logger.info(
                    "Streak win for user %s: %d days, saved $%.2f",
                    user.id,
                    win["streak_days"],
                    win["saved_amount"],
                )
                # TODO: send push notification via NotificationService
                # For now, log it — push integration happens in next sprint
                notified += 1
        except Exception as e:
            logger.error("Streak check failed for user %s: %s", user.id, e)
            errors += 1

    logger.info("Streak win cron done: %d notified, %d errors", notified, errors)

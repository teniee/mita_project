"""
3-Day Follow-up Reminder Cron Task
When a user ignored a budget warning, remind them 3 days later.
Based on MITA design principle: MITA is an advisor, not a judge.
"""
from typing import List, Dict
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.budget_thresholds import REMINDER_FOLLOWUP_DAYS
from app.core.logging_config import get_logger

logger = get_logger(__name__)

# In-memory store for ignored alerts (replace with DB table in future)
# Format: [(user_id_str, category, overspend_amount, alert_date, goal_title)]
_ignored_alerts: List[Dict] = []


def record_ignored_alert(
    user_id: str,
    category: str,
    overspend_amount: float,
    goal_title: str = None,
) -> None:
    """
    Record that a user ignored a budget alert.
    Call this from the notification handler when user taps [Ignore].
    """
    _ignored_alerts.append({
        "user_id": user_id,
        "category": category,
        "overspend_amount": overspend_amount,
        "goal_title": goal_title,
        "alert_date": datetime.now(timezone.utc).isoformat(),
        "reminded": False,
    })
    logger.info(f"User {user_id} ignored alert for {category} (${overspend_amount:.2f})")


def run_followup_reminders(db: Session) -> List[Dict]:
    """
    Cron task: send follow-up reminders for alerts ignored REMINDER_FOLLOWUP_DAYS ago.
    Returns list of reminders sent.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=REMINDER_FOLLOWUP_DAYS)
    reminders_sent = []

    for alert in _ignored_alerts:
        if alert.get("reminded"):
            continue

        alert_date = datetime.fromisoformat(alert["alert_date"])
        if alert_date > cutoff:
            continue  # Not 3 days yet

        # Build reminder message
        user_id = alert["user_id"]
        category = alert["category"]
        overspend = alert["overspend_amount"]
        goal_title = alert.get("goal_title")

        message = (
            f"3 days ago you overspent ${overspend:.2f} on {category}. "
        )
        if goal_title:
            message += f"Your goal [{goal_title}] is still waiting. Want to get back on track?"
        else:
            message += "Want to review your budget?"

        # Mark as reminded
        alert["reminded"] = True
        alert["reminded_at"] = now.isoformat()

        # Send actual push notification via NotificationIntegration
        try:
            from uuid import UUID
            from app.services.notification_integration import get_notification_integration
            notifier = get_notification_integration(db)
            notifier.send_custom_notification(
                user_id=UUID(user_id),
                title="Budget Follow-up 📊",
                message=message,
                notification_type="reminder",
                priority="medium",
                category=category,
            )
        except Exception as e:
            logger.warning(f"Failed to send follow-up push for user {user_id}: {e}")

        logger.info(f"Follow-up reminder sent to user {user_id}: {message}")
        reminders_sent.append({
            "user_id": user_id,
            "category": category,
            "message": message,
            "original_alert_date": alert["alert_date"],
        })

    return reminders_sent

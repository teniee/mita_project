"""
Daily Velocity Alert Cron Task

Runs once per day for every active, onboarded user with notifications enabled.
Checks spending velocity across all categories and sends proactive alerts +
positive win-streak notifications.

Integrates with the existing cron infrastructure:
- run_velocity_alerts_daily() — no-arg wrapper, called directly by rq_scheduler
- run_velocity_alerts_batch(db, today) — testable core, accepts injected session
"""
from datetime import date
from typing import Dict, Optional

from sqlalchemy.orm import Session

from app.core.logging_config import get_logger
from app.db.models import User
from app.services.velocity_alert_service import run_velocity_check_for_user

logger = get_logger(__name__)


def run_velocity_alerts_batch(
    db: Session,
    today: Optional[date] = None,
) -> Dict[str, int]:
    """
    Process all eligible users and send velocity alerts + win notifications.

    Args:
        db:    SQLAlchemy session.
        today: Override for "today" (useful in tests / back-filling).

    Returns:
        Summary dict: processed, alerts_sent, wins_sent, errors.
    """
    if today is None:
        today = date.today()

    summary = {
        "processed": 0,
        "alerts_sent": 0,
        "wins_sent": 0,
        "errors": 0,
    }

    # Only process users who: completed onboarding AND have notifications on
    users = (
        db.query(User)
        .filter(
            User.has_onboarded.is_(True),
            User.notifications_enabled.is_(True),
        )
        .all()
    )

    logger.info("velocity alerts cron: processing %d users for %s", len(users), today)

    for user in users:
        try:
            result = run_velocity_check_for_user(db=db, user_id=user.id, today=today)
            summary["processed"] += 1

            if result is not None:
                summary["alerts_sent"] += len(result.alerts)
                summary["wins_sent"] += len(result.wins)

        except Exception as exc:
            summary["errors"] += 1
            logger.error(
                "velocity cron error: user=%s err=%s", user.id, exc
            )

    logger.info(
        "velocity alerts cron complete: processed=%d alerts=%d wins=%d errors=%d",
        summary["processed"],
        summary["alerts_sent"],
        summary["wins_sent"],
        summary["errors"],
    )

    return summary


def run_velocity_alerts_daily() -> None:
    """
    No-arg scheduler entrypoint — mirrors the pattern used by
    run_streak_win_check() and run_followup_reminders().

    Creates its own DB session so rq_scheduler can call it directly.
    """
    from app.core.session import get_db

    db: Session = next(get_db())
    try:
        run_velocity_alerts_batch(db=db)
    finally:
        db.close()

"""
Scheduled Notifications Service
Handles periodic notifications like daily reminders, overdue goals, etc.
Should be run as background tasks via cron or task scheduler
"""
from datetime import datetime, date, timedelta
from typing import List, Dict
from uuid import UUID
import logging
import random

from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from app.db.models import Goal, User
from app.services.notification_integration import get_notification_integration
from app.services.notification_templates import FINANCIAL_TIPS
from app.services.core.engine.budget_tracker import BudgetTracker

logger = logging.getLogger(__name__)


class ScheduledNotificationService:
    """
    Service for sending scheduled/periodic notifications
    These should be called by background tasks or cron jobs
    """

    def __init__(self, db: Session):
        self.db = db
        self.notifier = get_notification_integration(db)

    # ============================================================================
    # DAILY NOTIFICATIONS
    # ============================================================================

    def send_daily_budget_reminders(self) -> Dict[str, int]:
        """
        Send daily budget reminders to all users
        Should be run every morning (e.g., 8 AM user's local time)

        Returns:
            Dict with counts of notifications sent
        """
        stats = {"sent": 0, "failed": 0}

        try:
            # Get all active users
            users = self.db.query(User).filter(User.is_active == True).all()

            today = date.today()
            year = today.year
            month = today.month
            days_in_month = (date(year, month + 1, 1) - timedelta(days=1)).day if month < 12 else 31
            days_left = days_in_month - today.day + 1

            for user in users:
                try:
                    # Get user's budget for current month
                    # Note: This is simplified - in production, get actual user budget from settings
                    tracker = BudgetTracker(self.db, user.id, year, month)
                    remaining_per_category = tracker.get_remaining_per_category()

                    # Calculate total remaining budget
                    total_remaining = sum(
                        amount for amount in remaining_per_category.values() if amount > 0
                    )

                    if total_remaining > 0:
                        self.notifier.notify_daily_budget_reminder(
                            user_id=user.id,
                            remaining_budget=float(total_remaining),
                            days_left=days_left
                        )
                        stats["sent"] += 1

                except Exception as e:
                    logger.error(f"Failed to send daily reminder to user {user.id}: {e}")
                    stats["failed"] += 1

        except Exception as e:
            logger.error(f"Error in send_daily_budget_reminders: {e}")

        logger.info(f"Daily budget reminders: {stats['sent']} sent, {stats['failed']} failed")
        return stats

    def send_motivational_tips(self, max_users: int = 100) -> Dict[str, int]:
        """
        Send random motivational financial tips to a subset of users
        Should be run daily or every few days

        Args:
            max_users: Maximum number of users to send tips to per run

        Returns:
            Dict with counts of notifications sent
        """
        stats = {"sent": 0, "failed": 0}

        try:
            # Get random active users (limit to avoid spam)
            users = (
                self.db.query(User)
                .filter(User.is_active == True)
                .order_by(func.random())
                .limit(max_users)
                .all()
            )

            # Pick a random tip
            tip = random.choice(FINANCIAL_TIPS)

            for user in users:
                try:
                    self.notifier.send_custom_notification(
                        user_id=user.id,
                        title="💪 Financial Tip",
                        message=tip,
                        notification_type="tip",
                        priority="low",
                        category="daily_reminders",
                        send_push=False  # Don't push, just in-app
                    )
                    stats["sent"] += 1

                except Exception as e:
                    logger.error(f"Failed to send tip to user {user.id}: {e}")
                    stats["failed"] += 1

        except Exception as e:
            logger.error(f"Error in send_motivational_tips: {e}")

        logger.info(f"Motivational tips: {stats['sent']} sent, {stats['failed']} failed")
        return stats

    # ============================================================================
    # GOAL MONITORING
    # ============================================================================

    def check_overdue_goals(self) -> Dict[str, int]:
        """
        Check for overdue goals and send reminders
        Should be run daily

        Returns:
            Dict with counts of notifications sent
        """
        stats = {"sent": 0, "failed": 0}

        try:
            today = date.today()

            # Find goals that are overdue (target_date < today and status = active)
            overdue_goals = (
                self.db.query(Goal)
                .filter(
                    and_(
                        Goal.status == 'active',
                        Goal.target_date < today,
                        Goal.target_date.isnot(None)
                    )
                )
                .all()
            )

            for goal in overdue_goals:
                try:
                    days_overdue = (today - goal.target_date).days

                    # Only send reminder once a week for overdue goals
                    if days_overdue % 7 == 0:
                        self.notifier.notify_goal_overdue(
                            user_id=goal.user_id,
                            goal_title=goal.title,
                            days_overdue=days_overdue
                        )
                        stats["sent"] += 1

                except Exception as e:
                    logger.error(f"Failed to send overdue notification for goal {goal.id}: {e}")
                    stats["failed"] += 1

        except Exception as e:
            logger.error(f"Error in check_overdue_goals: {e}")

        logger.info(f"Overdue goal reminders: {stats['sent']} sent, {stats['failed']} failed")
        return stats

    def check_goals_due_soon(self) -> Dict[str, int]:
        """
        Check for goals due within 7 days and send reminders
        Should be run daily

        Returns:
            Dict with counts of notifications sent
        """
        stats = {"sent": 0, "failed": 0}

        try:
            today = date.today()
            week_from_now = today + timedelta(days=7)

            # Find goals due within 7 days
            due_soon_goals = (
                self.db.query(Goal)
                .filter(
                    and_(
                        Goal.status == 'active',
                        Goal.target_date <= week_from_now,
                        Goal.target_date >= today,
                        Goal.target_date.isnot(None)
                    )
                )
                .all()
            )

            for goal in due_soon_goals:
                try:
                    days_remaining = (goal.target_date - today).days
                    remaining_amount = float(goal.remaining_amount)

                    # Only send if there's still amount remaining
                    if remaining_amount > 0:
                        self.notifier.notify_goal_due_soon(
                            user_id=goal.user_id,
                            goal_title=goal.title,
                            days_remaining=days_remaining,
                            remaining_amount=remaining_amount
                        )
                        stats["sent"] += 1

                except Exception as e:
                    logger.error(f"Failed to send due soon notification for goal {goal.id}: {e}")
                    stats["failed"] += 1

        except Exception as e:
            logger.error(f"Error in check_goals_due_soon: {e}")

        logger.info(f"Goals due soon reminders: {stats['sent']} sent, {stats['failed']} failed")
        return stats

    # ============================================================================
    # WEEKLY SUMMARIES
    # ============================================================================

    def send_weekly_progress_reports(self) -> Dict[str, int]:
        """
        Send weekly progress reports to all users
        Should be run every Sunday evening

        Returns:
            Dict with counts of notifications sent
        """
        stats = {"sent": 0, "failed": 0}

        try:
            # Get all active users with goals
            users_with_goals = (
                self.db.query(User.id)
                .join(Goal, Goal.user_id == User.id)
                .filter(User.is_active == True)
                .distinct()
                .all()
            )

            one_week_ago = datetime.utcnow() - timedelta(days=7)

            for (user_id,) in users_with_goals:
                try:
                    # Count goals on track (progress > 0 and status active)
                    goals_on_track = (
                        self.db.query(func.count(Goal.id))
                        .filter(
                            and_(
                                Goal.user_id == user_id,
                                Goal.status == 'active',
                                Goal.progress > 0
                            )
                        )
                        .scalar() or 0
                    )

                    # Calculate savings this week
                    # This is simplified - in production, track actual savings transactions
                    goals = self.db.query(Goal).filter(
                        and_(
                            Goal.user_id == user_id,
                            Goal.status == 'active',
                            Goal.last_updated >= one_week_ago
                        )
                    ).all()

                    total_saved_this_week = sum(
                        float(goal.saved_amount) for goal in goals if goal.saved_amount
                    ) / len(goals) if goals else 0

                    if goals_on_track > 0 or total_saved_this_week > 0:
                        self.notifier.notify_weekly_progress(
                            user_id=user_id,
                            goals_on_track=goals_on_track,
                            total_saved_this_week=total_saved_this_week
                        )
                        stats["sent"] += 1

                except Exception as e:
                    logger.error(f"Failed to send weekly report to user {user_id}: {e}")
                    stats["failed"] += 1

        except Exception as e:
            logger.error(f"Error in send_weekly_progress_reports: {e}")

        logger.info(f"Weekly progress reports: {stats['sent']} sent, {stats['failed']} failed")
        return stats

    # ============================================================================
    # MASTER SCHEDULER
    # ============================================================================

    def run_all_scheduled_tasks(self) -> Dict[str, Dict[str, int]]:
        """
        Run all scheduled notification tasks
        This can be called by a single cron job

        Returns:
            Dict with results from all tasks
        """
        results = {}

        logger.info("Starting scheduled notification tasks...")

        # Daily tasks
        results["daily_reminders"] = self.send_daily_budget_reminders()
        results["overdue_goals"] = self.check_overdue_goals()
        results["due_soon_goals"] = self.check_goals_due_soon()

        # Weekly task (check if it's Sunday)
        if datetime.now().weekday() == 6:  # Sunday
            results["weekly_reports"] = self.send_weekly_progress_reports()

        # Motivational tips (run every 3 days)
        if datetime.now().day % 3 == 0:
            results["motivational_tips"] = self.send_motivational_tips(max_users=50)

        logger.info("Scheduled notification tasks completed")
        return results


# Helper function for easy access
def get_scheduled_notification_service(db: Session) -> ScheduledNotificationService:
    """Get ScheduledNotificationService instance"""
    return ScheduledNotificationService(db)


# Example cron job integration
"""
To run this as a cron job, add to crontab:

# Run daily at 8 AM
0 8 * * * python -c "from app.services.scheduled_notifications import run_scheduled_notifications; run_scheduled_notifications()"

Or use APScheduler in your FastAPI app:

from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()
scheduler.add_job(run_scheduled_notifications, 'cron', hour=8, minute=0)
scheduler.start()
"""


def run_scheduled_notifications():
    """
    Standalone function to run scheduled notifications
    Can be called from cron or background scheduler
    """
    from app.core.session import SessionLocal

    db = SessionLocal()
    try:
        service = ScheduledNotificationService(db)
        results = service.run_all_scheduled_tasks()
        logger.info(f"Scheduled notifications completed: {results}")
    except Exception as e:
        logger.error(f"Error running scheduled notifications: {e}")
    finally:
        db.close()

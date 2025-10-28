"""
Notification Integration Helper
Simplifies sending notifications from any module
"""
from typing import Optional, Dict, Any
from uuid import UUID
import logging

from sqlalchemy.orm import Session

from app.services.notification_service import NotificationService
from app.services.push_service import send_push_notification
from app.services.notification_templates import NotificationTemplates

logger = logging.getLogger(__name__)


class NotificationIntegration:
    """
    Helper class for easy notification integration across modules
    Handles both in-app notifications and push notifications
    """

    def __init__(self, db: Session):
        self.db = db
        self.service = NotificationService(db)
        self.templates = NotificationTemplates()

    # ============================================================================
    # GOAL NOTIFICATIONS
    # ============================================================================

    def notify_goal_created(self, user_id: UUID, goal_title: str, target_amount: float):
        """Send notification when goal is created"""
        try:
            template = self.templates.goal_created(goal_title, target_amount)
            notification = self.service.create_notification(
                user_id=user_id,
                send_immediately=True,
                **template
            )
            logger.info(f"Goal created notification sent to user {user_id}")
            return notification
        except Exception as e:
            logger.error(f"Failed to send goal created notification: {e}")
            return None

    def notify_goal_progress(
        self,
        user_id: UUID,
        goal_title: str,
        progress: float,
        saved_amount: float,
        target_amount: float
    ):
        """
        Send notification for goal progress milestones (25%, 50%, 75%, 90%)
        Only sends at specific milestones to avoid spam
        """
        try:
            # Check if this is a milestone worth notifying
            milestone_thresholds = [25, 50, 75, 90]
            is_milestone = any(abs(progress - threshold) < 1 for threshold in milestone_thresholds)

            if not is_milestone:
                return None

            template = self.templates.goal_progress_milestone(
                goal_title, progress, saved_amount, target_amount
            )
            notification = self.service.create_notification(
                user_id=user_id,
                send_immediately=True,
                **template
            )
            logger.info(f"Goal progress ({progress}%) notification sent to user {user_id}")
            return notification
        except Exception as e:
            logger.error(f"Failed to send goal progress notification: {e}")
            return None

    def notify_goal_completed(
        self,
        user_id: UUID,
        goal_title: str,
        final_amount: float,
        days_taken: Optional[int] = None
    ):
        """Send celebration notification when goal is completed"""
        try:
            template = self.templates.goal_completed(goal_title, final_amount, days_taken)
            notification = self.service.create_notification(
                user_id=user_id,
                send_immediately=True,
                **template
            )
            logger.info(f"Goal completed notification sent to user {user_id}")
            return notification
        except Exception as e:
            logger.error(f"Failed to send goal completed notification: {e}")
            return None

    def notify_goal_overdue(self, user_id: UUID, goal_title: str, days_overdue: int):
        """Send reminder for overdue goals"""
        try:
            template = self.templates.goal_overdue(goal_title, days_overdue)
            notification = self.service.create_notification(
                user_id=user_id,
                send_immediately=True,
                **template
            )
            logger.info(f"Goal overdue notification sent to user {user_id}")
            return notification
        except Exception as e:
            logger.error(f"Failed to send goal overdue notification: {e}")
            return None

    def notify_goal_due_soon(
        self,
        user_id: UUID,
        goal_title: str,
        days_remaining: int,
        remaining_amount: float
    ):
        """Send reminder when goal deadline is approaching"""
        try:
            template = self.templates.goal_due_soon(goal_title, days_remaining, remaining_amount)
            notification = self.service.create_notification(
                user_id=user_id,
                send_immediately=True,
                **template
            )
            logger.info(f"Goal due soon notification sent to user {user_id}")
            return notification
        except Exception as e:
            logger.error(f"Failed to send goal due soon notification: {e}")
            return None

    # ============================================================================
    # BUDGET NOTIFICATIONS
    # ============================================================================

    def notify_budget_warning(
        self,
        user_id: UUID,
        category: str,
        spent: float,
        limit: float,
        percentage: float
    ):
        """Send warning when budget reaches 80%"""
        try:
            template = self.templates.budget_warning(category, spent, limit, percentage)
            notification = self.service.create_notification(
                user_id=user_id,
                send_immediately=True,
                **template
            )
            logger.info(f"Budget warning notification sent to user {user_id} for {category}")
            return notification
        except Exception as e:
            logger.error(f"Failed to send budget warning notification: {e}")
            return None

    def notify_budget_exceeded(
        self,
        user_id: UUID,
        category: str,
        spent: float,
        limit: float,
        overage: float
    ):
        """Send alert when budget is exceeded"""
        try:
            template = self.templates.budget_exceeded(category, spent, limit, overage)
            notification = self.service.create_notification(
                user_id=user_id,
                send_immediately=True,
                **template
            )
            logger.info(f"Budget exceeded notification sent to user {user_id} for {category}")
            return notification
        except Exception as e:
            logger.error(f"Failed to send budget exceeded notification: {e}")
            return None

    def notify_monthly_budget_summary(
        self,
        user_id: UUID,
        total_spent: float,
        total_budget: float,
        categories_over: int
    ):
        """Send end of month budget summary"""
        try:
            template = self.templates.monthly_budget_summary(
                total_spent, total_budget, categories_over
            )
            notification = self.service.create_notification(
                user_id=user_id,
                send_immediately=True,
                **template
            )
            logger.info(f"Monthly budget summary sent to user {user_id}")
            return notification
        except Exception as e:
            logger.error(f"Failed to send monthly budget summary: {e}")
            return None

    # ============================================================================
    # TRANSACTION NOTIFICATIONS
    # ============================================================================

    def notify_large_transaction(
        self,
        user_id: UUID,
        amount: float,
        category: str,
        merchant: Optional[str] = None
    ):
        """Send notification for large transactions"""
        try:
            template = self.templates.large_transaction(amount, category, merchant)
            notification = self.service.create_notification(
                user_id=user_id,
                send_immediately=True,
                **template
            )
            logger.info(f"Large transaction notification sent to user {user_id}")
            return notification
        except Exception as e:
            logger.error(f"Failed to send large transaction notification: {e}")
            return None

    def notify_transaction_added_to_goal(
        self,
        user_id: UUID,
        amount: float,
        goal_title: str,
        new_progress: float
    ):
        """Send notification when transaction is linked to goal"""
        try:
            template = self.templates.transaction_added_to_goal(amount, goal_title, new_progress)
            notification = self.service.create_notification(
                user_id=user_id,
                send_immediately=True,
                **template
            )
            logger.info(f"Transaction goal link notification sent to user {user_id}")
            return notification
        except Exception as e:
            logger.error(f"Failed to send transaction goal notification: {e}")
            return None

    # ============================================================================
    # AI & INSIGHTS NOTIFICATIONS
    # ============================================================================

    def notify_ai_recommendation(
        self,
        user_id: UUID,
        recommendation: str,
        potential_savings: Optional[float] = None
    ):
        """Send AI-generated recommendation"""
        try:
            template = self.templates.ai_recommendation(recommendation, potential_savings)
            notification = self.service.create_notification(
                user_id=user_id,
                send_immediately=True,
                **template
            )
            logger.info(f"AI recommendation sent to user {user_id}")
            return notification
        except Exception as e:
            logger.error(f"Failed to send AI recommendation: {e}")
            return None

    def notify_savings_opportunity(
        self,
        user_id: UUID,
        category: str,
        amount: float
    ):
        """Send notification about savings opportunity"""
        try:
            template = self.templates.savings_opportunity(category, amount)
            notification = self.service.create_notification(
                user_id=user_id,
                send_immediately=True,
                **template
            )
            logger.info(f"Savings opportunity notification sent to user {user_id}")
            return notification
        except Exception as e:
            logger.error(f"Failed to send savings opportunity notification: {e}")
            return None

    # ============================================================================
    # DAILY REMINDERS
    # ============================================================================

    def notify_daily_budget_reminder(
        self,
        user_id: UUID,
        remaining_budget: float,
        days_left: int
    ):
        """Send daily budget reminder"""
        try:
            template = self.templates.daily_budget_reminder(remaining_budget, days_left)
            notification = self.service.create_notification(
                user_id=user_id,
                send_immediately=True,
                **template
            )
            logger.info(f"Daily budget reminder sent to user {user_id}")
            return notification
        except Exception as e:
            logger.error(f"Failed to send daily budget reminder: {e}")
            return None

    def notify_weekly_progress(
        self,
        user_id: UUID,
        goals_on_track: int,
        total_saved_this_week: float
    ):
        """Send weekly progress report"""
        try:
            template = self.templates.weekly_progress_report(goals_on_track, total_saved_this_week)
            notification = self.service.create_notification(
                user_id=user_id,
                send_immediately=True,
                **template
            )
            logger.info(f"Weekly progress report sent to user {user_id}")
            return notification
        except Exception as e:
            logger.error(f"Failed to send weekly progress report: {e}")
            return None

    # ============================================================================
    # GENERIC NOTIFICATION HELPER
    # ============================================================================

    def send_custom_notification(
        self,
        user_id: UUID,
        title: str,
        message: str,
        notification_type: str = "info",
        priority: str = "medium",
        category: Optional[str] = None,
        image_url: Optional[str] = None,
        action_url: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        send_push: bool = True
    ):
        """
        Send a custom notification with full control
        Useful for one-off notifications that don't fit templates
        """
        try:
            notification = self.service.create_notification(
                user_id=user_id,
                title=title,
                message=message,
                type=notification_type,
                priority=priority,
                category=category,
                image_url=image_url,
                action_url=action_url,
                data=data,
                send_immediately=send_push
            )
            logger.info(f"Custom notification sent to user {user_id}")
            return notification
        except Exception as e:
            logger.error(f"Failed to send custom notification: {e}")
            return None


# Convenience function for quick access
def get_notification_integration(db: Session) -> NotificationIntegration:
    """Get NotificationIntegration instance"""
    return NotificationIntegration(db)

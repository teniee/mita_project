"""
Notification Service - Complete notification management with rich features
Handles creation, delivery, scheduling, and tracking of all notifications
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.db.models.notification import (
    Notification,
    NotificationPriority,
    NotificationStatus,
    NotificationType,
)
from app.db.models.push_token import PushToken
from app.db.models.user import User
from app.services.notification_log_service import log_notification
from app.services.push_service import send_push_notification

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for managing notifications"""

    def __init__(self, db: Session):
        self.db = db

    def create_notification(
        self,
        user_id: UUID,
        title: str,
        message: str,
        type: str = NotificationType.INFO.value,
        priority: str = NotificationPriority.MEDIUM.value,
        image_url: Optional[str] = None,
        action_url: Optional[str] = None,
        data: Optional[Dict] = None,
        category: Optional[str] = None,
        group_key: Optional[str] = None,
        scheduled_for: Optional[datetime] = None,
        expires_at: Optional[datetime] = None,
        send_immediately: bool = True,
    ) -> Notification:
        """
        Create a new notification for a user

        Args:
            user_id: User ID to send notification to
            title: Notification title
            message: Notification message
            type: Notification type (alert, warning, info, tip, achievement, reminder, recommendation)
            priority: Priority level (low, medium, high, critical)
            image_url: Optional image URL for rich notifications
            action_url: Optional deep link URL
            data: Optional structured data
            category: Optional category (budget, transaction, goal, etc.)
            group_key: Optional key for grouping related notifications
            scheduled_for: Optional scheduled time
            expires_at: Optional expiration time
            send_immediately: Whether to send notification immediately via push/email

        Returns:
            Created notification object
        """
        notification = Notification(
            user_id=user_id,
            title=title,
            message=message,
            type=type,
            priority=priority,
            image_url=image_url,
            action_url=action_url,
            data=data,
            category=category,
            group_key=group_key,
            scheduled_for=scheduled_for,
            expires_at=expires_at,
            status=NotificationStatus.PENDING.value if scheduled_for else NotificationStatus.SENT.value,
        )

        self.db.add(notification)
        self.db.commit()
        self.db.refresh(notification)

        # Send immediately if requested and not scheduled
        if send_immediately and not scheduled_for:
            self._deliver_notification(notification)

        logger.info(
            f"Created notification {notification.id} for user {user_id} - Type: {type}, Priority: {priority}"
        )
        return notification

    def _send_email_fallback(self, notification: Notification) -> bool:
        """
        Send notification via email as fallback when push fails

        Args:
            notification: Notification to send via email

        Returns:
            True if email sent successfully, False otherwise
        """
        try:
            # Get user email
            user = self.db.query(User).filter(User.id == notification.user_id).first()
            if not user or not user.email:
                logger.warning(
                    f"Cannot send email fallback for notification {notification.id} - no email found"
                )
                return False

            # Import email service here to avoid circular imports
            from app.services.email_service import EmailService, EmailType, EmailPriority
            from app.core.config import settings
            from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
            from sqlalchemy.orm import sessionmaker

            # Create async database session for email service
            async def send_email_async():
                engine = create_async_engine(settings.ASYNC_DATABASE_URL)
                async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
                async with async_session() as session:
                    email_service = EmailService()

                    # Map notification priority to email priority
                    email_priority = EmailPriority.NORMAL
                    if notification.priority == NotificationPriority.HIGH.value:
                        email_priority = EmailPriority.HIGH
                    elif notification.priority == NotificationPriority.LOW.value:
                        email_priority = EmailPriority.LOW

                    # Determine email type based on notification category
                    email_type = EmailType.WELCOME  # Default
                    if notification.category == "budget":
                        email_type = EmailType.BUDGET_ALERT
                    elif notification.category == "security":
                        email_type = EmailType.SECURITY_ALERT
                    elif notification.category == "transaction":
                        email_type = EmailType.TRANSACTION_CONFIRMATION

                    # Prepare email variables
                    variables = {
                        "title": notification.title,
                        "message": notification.message,
                        "action_url": notification.action_url or "",
                        "user_name": user.full_name or user.email,
                    }

                    # Send email
                    result = await email_service.send_email(
                        to_email=user.email,
                        email_type=email_type,
                        variables=variables,
                        priority=email_priority,
                        user_id=str(user.id),
                        db=session
                    )

                    return result.success

            # Run async function synchronously
            success = asyncio.run(send_email_async())

            if success:
                notification.channel = "email"
                notification.status = NotificationStatus.DELIVERED.value
                notification.sent_at = datetime.utcnow()
                notification.delivered_at = datetime.utcnow()
                self.db.commit()

                # Log successful email delivery
                log_notification(
                    self.db,
                    user_id=notification.user_id,
                    channel="email",
                    message=f"{notification.title}: {notification.message}",
                    success=True,
                )

                logger.info(
                    f"Successfully delivered notification {notification.id} via email fallback"
                )
                return True
            else:
                logger.error(f"Email fallback failed for notification {notification.id}")
                return False

        except Exception as e:
            logger.error(f"Error in email fallback for notification {notification.id}: {e}")
            return False

    def _deliver_notification(self, notification: Notification) -> bool:
        """
        Deliver notification via push notification or email

        Args:
            notification: Notification to deliver

        Returns:
            True if delivered successfully, False otherwise
        """
        try:
            # Get user's push tokens
            push_tokens = (
                self.db.query(PushToken)
                .filter(PushToken.user_id == notification.user_id)
                .all()
            )

            if push_tokens:
                # Try push notification
                for push_token in push_tokens:
                    try:
                        # Build notification data
                        fcm_data = {
                            "notification_id": str(notification.id),
                            "type": notification.type,
                            "priority": notification.priority,
                            "category": notification.category or "",
                        }

                        if notification.action_url:
                            fcm_data["action_url"] = notification.action_url

                        if notification.data:
                            fcm_data.update(notification.data)

                        # Send via FCM
                        success = send_push_notification(
                            token=push_token.token,
                            title=notification.title,
                            body=notification.message,
                            data=fcm_data,
                            image_url=notification.image_url,
                            user_id=notification.user_id,
                            db=self.db,
                        )

                        if success:
                            notification.status = NotificationStatus.DELIVERED.value
                            notification.channel = "push"
                            notification.sent_at = datetime.utcnow()
                            notification.delivered_at = datetime.utcnow()
                            self.db.commit()

                            # Log successful delivery
                            log_notification(
                                self.db,
                                user_id=notification.user_id,
                                channel="push",
                                message=f"{notification.title}: {notification.message}",
                                success=True,
                            )

                            logger.info(
                                f"Successfully delivered notification {notification.id} via push"
                            )
                            return True
                    except Exception as e:
                        logger.error(f"Error sending push notification: {e}")
                        continue

            # Fallback to email if push fails
            logger.warning(
                f"Push notification failed for {notification.id} - attempting email fallback"
            )

            email_success = self._send_email_fallback(notification)
            if email_success:
                return True

            # Both push and email failed
            notification.status = NotificationStatus.FAILED.value
            notification.error_message = "Both push and email delivery failed"
            self.db.commit()

            logger.error(
                f"Failed to deliver notification {notification.id} via both push and email"
            )
            return False

        except Exception as e:
            logger.error(f"Error delivering notification {notification.id}: {e}")
            notification.status = NotificationStatus.FAILED.value
            notification.error_message = str(e)
            self.db.commit()
            return False

    def get_user_notifications(
        self,
        user_id: UUID,
        limit: int = 50,
        offset: int = 0,
        unread_only: bool = False,
        notification_type: Optional[str] = None,
        priority: Optional[str] = None,
        category: Optional[str] = None,
    ) -> List[Notification]:
        """
        Get notifications for a user with optional filters

        Args:
            user_id: User ID
            limit: Maximum number of notifications to return
            offset: Offset for pagination
            unread_only: Only return unread notifications
            notification_type: Filter by notification type
            priority: Filter by priority level
            category: Filter by category

        Returns:
            List of notifications
        """
        query = self.db.query(Notification).filter(Notification.user_id == user_id)

        # Apply filters
        if unread_only:
            query = query.filter(Notification.is_read == False)

        if notification_type:
            query = query.filter(Notification.type == notification_type)

        if priority:
            query = query.filter(Notification.priority == priority)

        if category:
            query = query.filter(Notification.category == category)

        # Filter out expired notifications
        query = query.filter(
            or_(
                Notification.expires_at.is_(None),
                Notification.expires_at > datetime.utcnow(),
            )
        )

        # Order by creation date (newest first)
        query = query.order_by(Notification.created_at.desc())

        # Apply pagination
        query = query.limit(limit).offset(offset)

        return query.all()

    def get_notification_by_id(
        self, notification_id: UUID, user_id: UUID
    ) -> Optional[Notification]:
        """Get a specific notification by ID for a user"""
        return (
            self.db.query(Notification)
            .filter(
                and_(
                    Notification.id == notification_id,
                    Notification.user_id == user_id,
                )
            )
            .first()
        )

    def mark_as_read(
        self, notification_id: UUID, user_id: UUID
    ) -> Optional[Notification]:
        """Mark a notification as read"""
        notification = self.get_notification_by_id(notification_id, user_id)

        if notification and not notification.is_read:
            notification.is_read = True
            notification.read_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(notification)

            logger.info(f"Marked notification {notification_id} as read for user {user_id}")

        return notification

    def mark_all_as_read(self, user_id: UUID) -> int:
        """Mark all notifications as read for a user"""
        notifications = (
            self.db.query(Notification)
            .filter(
                and_(
                    Notification.user_id == user_id,
                    Notification.is_read == False,
                )
            )
            .all()
        )

        for notification in notifications:
            notification.is_read = True
            notification.read_at = datetime.utcnow()

        self.db.commit()

        count = len(notifications)
        logger.info(f"Marked {count} notifications as read for user {user_id}")
        return count

    def delete_notification(
        self, notification_id: UUID, user_id: UUID
    ) -> bool:
        """Delete a notification"""
        notification = self.get_notification_by_id(notification_id, user_id)

        if notification:
            self.db.delete(notification)
            self.db.commit()
            logger.info(f"Deleted notification {notification_id} for user {user_id}")
            return True

        return False

    def get_unread_count(self, user_id: UUID) -> int:
        """Get count of unread notifications for a user"""
        return (
            self.db.query(Notification)
            .filter(
                and_(
                    Notification.user_id == user_id,
                    Notification.is_read == False,
                    or_(
                        Notification.expires_at.is_(None),
                        Notification.expires_at > datetime.utcnow(),
                    ),
                )
            )
            .count()
        )

    def send_scheduled_notifications(self):
        """
        Send all notifications that are scheduled for delivery
        Should be called by a cron job or background task
        """
        now = datetime.utcnow()

        scheduled_notifications = (
            self.db.query(Notification)
            .filter(
                and_(
                    Notification.status == NotificationStatus.PENDING.value,
                    Notification.scheduled_for <= now,
                )
            )
            .all()
        )

        logger.info(f"Found {len(scheduled_notifications)} scheduled notifications to send")

        for notification in scheduled_notifications:
            self._deliver_notification(notification)

    def cleanup_old_notifications(self, days: int = 30):
        """
        Clean up old notifications (older than specified days)
        Should be called by a cron job
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        old_notifications = (
            self.db.query(Notification)
            .filter(
                or_(
                    Notification.created_at < cutoff_date,
                    and_(
                        Notification.expires_at.isnot(None),
                        Notification.expires_at < datetime.utcnow(),
                    ),
                )
            )
            .all()
        )

        for notification in old_notifications:
            self.db.delete(notification)

        self.db.commit()

        count = len(old_notifications)
        logger.info(f"Cleaned up {count} old notifications")
        return count

    def get_grouped_notifications(
        self, user_id: UUID, group_key: str
    ) -> List[Notification]:
        """Get all notifications with a specific group key"""
        return (
            self.db.query(Notification)
            .filter(
                and_(
                    Notification.user_id == user_id,
                    Notification.group_key == group_key,
                )
            )
            .order_by(Notification.created_at.desc())
            .all()
        )


# Convenience functions for creating common notification types

def send_budget_alert(
    db: Session,
    user_id: UUID,
    budget_name: str,
    spent_amount: float,
    budget_limit: float,
    percentage: float,
) -> Notification:
    """Send a budget alert notification"""
    service = NotificationService(db)

    return service.create_notification(
        user_id=user_id,
        title=f"Budget Alert: {budget_name}",
        message=f"You've spent {percentage}% of your {budget_name} budget (${spent_amount:.2f} of ${budget_limit:.2f})",
        type=NotificationType.ALERT.value if percentage >= 100 else NotificationType.WARNING.value,
        priority=NotificationPriority.HIGH.value if percentage >= 100 else NotificationPriority.MEDIUM.value,
        category="budget",
        group_key=f"budget_{budget_name}",
    )


def send_goal_achievement(
    db: Session,
    user_id: UUID,
    goal_name: str,
    achieved_amount: float,
) -> Notification:
    """Send a goal achievement notification"""
    service = NotificationService(db)

    return service.create_notification(
        user_id=user_id,
        title="Goal Achieved!",
        message=f"Congratulations! You've reached your goal: {goal_name} (${achieved_amount:.2f})",
        type=NotificationType.ACHIEVEMENT.value,
        priority=NotificationPriority.HIGH.value,
        category="goal",
    )


def send_daily_reminder(
    db: Session,
    user_id: UUID,
    message: str,
) -> Notification:
    """Send a daily reminder notification"""
    service = NotificationService(db)

    return service.create_notification(
        user_id=user_id,
        title="Daily Reminder",
        message=message,
        type=NotificationType.REMINDER.value,
        priority=NotificationPriority.LOW.value,
        category="daily_checkpoint",
    )


def send_ai_recommendation(
    db: Session,
    user_id: UUID,
    title: str,
    message: str,
    action_url: Optional[str] = None,
) -> Notification:
    """Send an AI-generated recommendation"""
    service = NotificationService(db)

    return service.create_notification(
        user_id=user_id,
        title=title,
        message=message,
        type=NotificationType.RECOMMENDATION.value,
        priority=NotificationPriority.MEDIUM.value,
        category="ai_advice",
        action_url=action_url,
    )


def send_transaction_alert(
    db: Session,
    user_id: UUID,
    amount: float,
    merchant: str,
    category: str,
) -> Notification:
    """Send a transaction alert notification"""
    service = NotificationService(db)

    return service.create_notification(
        user_id=user_id,
        title="New Transaction",
        message=f"${amount:.2f} spent at {merchant}",
        type=NotificationType.INFO.value,
        priority=NotificationPriority.LOW.value,
        category="transaction",
        data={
            "amount": amount,
            "merchant": merchant,
            "category": category,
        },
    )

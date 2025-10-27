"""
Notification Service - Complete notification management with rich features
Handles creation, delivery, scheduling, and tracking of all notifications
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.models.notification import (
    Notification,
    NotificationPriority,
    NotificationStatus,
    NotificationType,
)
from app.db.models.push_token import PushToken
from app.services.notification_log_service import log_notification
from app.services.push_service import send_push_notification

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for managing notifications"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_notification(
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
        await self.db.commit()
        await self.db.refresh(notification)

        # Send immediately if requested and not scheduled
        if send_immediately and not scheduled_for:
            await self._deliver_notification(notification)

        logger.info(
            f"Created notification {notification.id} for user {user_id} - Type: {type}, Priority: {priority}"
        )
        return notification

    async def _deliver_notification(self, notification: Notification) -> bool:
        """
        Deliver notification via push notification or email

        Args:
            notification: Notification to deliver

        Returns:
            True if delivered successfully, False otherwise
        """
        try:
            # Get user's push tokens
            result = await self.db.execute(
                select(PushToken).where(PushToken.user_id == notification.user_id)
            )
            push_tokens = result.scalars().all()

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
                        success = await send_push_notification(
                            token=push_token.token,
                            title=notification.title,
                            body=notification.message,
                            data=fcm_data,
                            image_url=notification.image_url,
                        )

                        if success:
                            notification.status = NotificationStatus.DELIVERED.value
                            notification.channel = "push"
                            notification.sent_at = datetime.utcnow()
                            notification.delivered_at = datetime.utcnow()
                            await self.db.commit()

                            # Log successful delivery
                            await log_notification(
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

            # TODO: Fallback to email if push fails
            notification.status = NotificationStatus.FAILED.value
            notification.error_message = "No valid push tokens found"
            await self.db.commit()

            logger.warning(
                f"Failed to deliver notification {notification.id} - No push tokens"
            )
            return False

        except Exception as e:
            logger.error(f"Error delivering notification {notification.id}: {e}")
            notification.status = NotificationStatus.FAILED.value
            notification.error_message = str(e)
            await self.db.commit()
            return False

    async def get_user_notifications(
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
        query = select(Notification).where(Notification.user_id == user_id)

        # Apply filters
        if unread_only:
            query = query.where(Notification.is_read == False)

        if notification_type:
            query = query.where(Notification.type == notification_type)

        if priority:
            query = query.where(Notification.priority == priority)

        if category:
            query = query.where(Notification.category == category)

        # Filter out expired notifications
        query = query.where(
            or_(
                Notification.expires_at.is_(None),
                Notification.expires_at > datetime.utcnow(),
            )
        )

        # Order by creation date (newest first)
        query = query.order_by(Notification.created_at.desc())

        # Apply pagination
        query = query.limit(limit).offset(offset)

        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_notification_by_id(
        self, notification_id: UUID, user_id: UUID
    ) -> Optional[Notification]:
        """Get a specific notification by ID for a user"""
        result = await self.db.execute(
            select(Notification).where(
                and_(
                    Notification.id == notification_id,
                    Notification.user_id == user_id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def mark_as_read(
        self, notification_id: UUID, user_id: UUID
    ) -> Optional[Notification]:
        """Mark a notification as read"""
        notification = await self.get_notification_by_id(notification_id, user_id)

        if notification and not notification.is_read:
            notification.is_read = True
            notification.read_at = datetime.utcnow()
            await self.db.commit()
            await self.db.refresh(notification)

            logger.info(f"Marked notification {notification_id} as read for user {user_id}")

        return notification

    async def mark_all_as_read(self, user_id: UUID) -> int:
        """Mark all notifications as read for a user"""
        result = await self.db.execute(
            select(Notification).where(
                and_(
                    Notification.user_id == user_id,
                    Notification.is_read == False,
                )
            )
        )
        notifications = result.scalars().all()

        for notification in notifications:
            notification.is_read = True
            notification.read_at = datetime.utcnow()

        await self.db.commit()

        count = len(notifications)
        logger.info(f"Marked {count} notifications as read for user {user_id}")
        return count

    async def delete_notification(
        self, notification_id: UUID, user_id: UUID
    ) -> bool:
        """Delete a notification"""
        notification = await self.get_notification_by_id(notification_id, user_id)

        if notification:
            await self.db.delete(notification)
            await self.db.commit()
            logger.info(f"Deleted notification {notification_id} for user {user_id}")
            return True

        return False

    async def get_unread_count(self, user_id: UUID) -> int:
        """Get count of unread notifications for a user"""
        result = await self.db.execute(
            select(Notification).where(
                and_(
                    Notification.user_id == user_id,
                    Notification.is_read == False,
                    or_(
                        Notification.expires_at.is_(None),
                        Notification.expires_at > datetime.utcnow(),
                    ),
                )
            )
        )
        return len(result.scalars().all())

    async def send_scheduled_notifications(self):
        """
        Send all notifications that are scheduled for delivery
        Should be called by a cron job or background task
        """
        now = datetime.utcnow()

        result = await self.db.execute(
            select(Notification).where(
                and_(
                    Notification.status == NotificationStatus.PENDING.value,
                    Notification.scheduled_for <= now,
                )
            )
        )
        scheduled_notifications = result.scalars().all()

        logger.info(f"Found {len(scheduled_notifications)} scheduled notifications to send")

        for notification in scheduled_notifications:
            await self._deliver_notification(notification)

    async def cleanup_old_notifications(self, days: int = 30):
        """
        Clean up old notifications (older than specified days)
        Should be called by a cron job
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        result = await self.db.execute(
            select(Notification).where(
                or_(
                    Notification.created_at < cutoff_date,
                    and_(
                        Notification.expires_at.isnot(None),
                        Notification.expires_at < datetime.utcnow(),
                    ),
                )
            )
        )
        old_notifications = result.scalars().all()

        for notification in old_notifications:
            await self.db.delete(notification)

        await self.db.commit()

        count = len(old_notifications)
        logger.info(f"Cleaned up {count} old notifications")
        return count

    async def get_grouped_notifications(
        self, user_id: UUID, group_key: str
    ) -> List[Notification]:
        """Get all notifications with a specific group key"""
        result = await self.db.execute(
            select(Notification).where(
                and_(
                    Notification.user_id == user_id,
                    Notification.group_key == group_key,
                )
            ).order_by(Notification.created_at.desc())
        )
        return result.scalars().all()


# Convenience functions for creating common notification types

async def send_budget_alert(
    db: AsyncSession,
    user_id: UUID,
    budget_name: str,
    spent_amount: float,
    budget_limit: float,
    percentage: float,
) -> Notification:
    """Send a budget alert notification"""
    service = NotificationService(db)

    return await service.create_notification(
        user_id=user_id,
        title=f"Budget Alert: {budget_name}",
        message=f"You've spent {percentage}% of your {budget_name} budget (${spent_amount:.2f} of ${budget_limit:.2f})",
        type=NotificationType.ALERT.value if percentage >= 100 else NotificationType.WARNING.value,
        priority=NotificationPriority.HIGH.value if percentage >= 100 else NotificationPriority.MEDIUM.value,
        category="budget",
        group_key=f"budget_{budget_name}",
    )


async def send_goal_achievement(
    db: AsyncSession,
    user_id: UUID,
    goal_name: str,
    achieved_amount: float,
) -> Notification:
    """Send a goal achievement notification"""
    service = NotificationService(db)

    return await service.create_notification(
        user_id=user_id,
        title="Goal Achieved!",
        message=f"Congratulations! You've reached your goal: {goal_name} (${achieved_amount:.2f})",
        type=NotificationType.ACHIEVEMENT.value,
        priority=NotificationPriority.HIGH.value,
        category="goal",
    )


async def send_daily_reminder(
    db: AsyncSession,
    user_id: UUID,
    message: str,
) -> Notification:
    """Send a daily reminder notification"""
    service = NotificationService(db)

    return await service.create_notification(
        user_id=user_id,
        title="Daily Reminder",
        message=message,
        type=NotificationType.REMINDER.value,
        priority=NotificationPriority.LOW.value,
        category="daily_checkpoint",
    )


async def send_ai_recommendation(
    db: AsyncSession,
    user_id: UUID,
    title: str,
    message: str,
    action_url: Optional[str] = None,
) -> Notification:
    """Send an AI-generated recommendation"""
    service = NotificationService(db)

    return await service.create_notification(
        user_id=user_id,
        title=title,
        message=message,
        type=NotificationType.RECOMMENDATION.value,
        priority=NotificationPriority.MEDIUM.value,
        category="ai_advice",
        action_url=action_url,
    )


async def send_transaction_alert(
    db: AsyncSession,
    user_id: UUID,
    amount: float,
    merchant: str,
    category: str,
) -> Notification:
    """Send a transaction alert notification"""
    service = NotificationService(db)

    return await service.create_notification(
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

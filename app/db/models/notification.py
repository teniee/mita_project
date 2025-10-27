import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, Column, DateTime, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID

from .base import Base


class NotificationType(str, Enum):
    """Notification types"""
    ALERT = "alert"  # Critical financial alerts
    WARNING = "warning"  # Budget warnings
    INFO = "info"  # General information
    TIP = "tip"  # Financial tips and advice
    ACHIEVEMENT = "achievement"  # Milestones and achievements
    REMINDER = "reminder"  # Daily checkpoints and reminders
    RECOMMENDATION = "recommendation"  # AI-generated recommendations


class NotificationPriority(str, Enum):
    """Notification priority levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class NotificationStatus(str, Enum):
    """Notification delivery status"""
    PENDING = "pending"  # Scheduled but not sent yet
    SENT = "sent"  # Successfully sent
    DELIVERED = "delivered"  # Confirmed delivered to device
    READ = "read"  # User has read the notification
    FAILED = "failed"  # Failed to deliver
    CANCELLED = "cancelled"  # Cancelled before sending


class Notification(Base):
    """
    Main notification model for storing all user notifications.
    Supports rich content, scheduling, and delivery tracking.
    """
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    # Content
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    type = Column(String(50), nullable=False, default=NotificationType.INFO.value)
    priority = Column(String(20), nullable=False, default=NotificationPriority.MEDIUM.value)

    # Rich content support
    image_url = Column(String(500), nullable=True)
    action_url = Column(String(500), nullable=True)  # Deep link URL
    data = Column(JSON, nullable=True)  # Additional structured data

    # Delivery tracking
    status = Column(String(20), nullable=False, default=NotificationStatus.PENDING.value)
    channel = Column(String(20), nullable=True)  # 'push', 'email', 'in_app'

    # Read tracking
    is_read = Column(Boolean, default=False, index=True)
    read_at = Column(DateTime(timezone=True), nullable=True)

    # Scheduling
    scheduled_for = Column(DateTime(timezone=True), nullable=True, index=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    delivered_at = Column(DateTime(timezone=True), nullable=True)

    # Error tracking
    error_message = Column(Text, nullable=True)
    retry_count = Column(String, default="0")

    # Metadata
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    expires_at = Column(DateTime(timezone=True), nullable=True)  # Notification expiry

    # Grouping and categorization
    category = Column(String(50), nullable=True)  # 'budget', 'transaction', 'goal', etc.
    group_key = Column(String(100), nullable=True, index=True)  # For grouping related notifications

    def to_dict(self):
        """Convert notification to dictionary"""
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "title": self.title,
            "message": self.message,
            "type": self.type,
            "priority": self.priority,
            "image_url": self.image_url,
            "action_url": self.action_url,
            "data": self.data,
            "status": self.status,
            "channel": self.channel,
            "is_read": self.is_read,
            "read_at": self.read_at.isoformat() if self.read_at else None,
            "scheduled_for": self.scheduled_for.isoformat() if self.scheduled_for else None,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "delivered_at": self.delivered_at.isoformat() if self.delivered_at else None,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "category": self.category,
            "group_key": self.group_key,
        }

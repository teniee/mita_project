from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.schemas.base import UserOwnedResponseSchema


# Existing schemas
class TokenIn(BaseModel):
    token: str
    platform: str = "fcm"


class NotificationTest(BaseModel):
    message: str
    token: Optional[str] = None
    email: Optional[EmailStr] = None
    platform: Optional[str] = None


# New notification schemas
class NotificationCreate(BaseModel):
    """Schema for creating a new notification"""
    title: str = Field(..., min_length=1, max_length=255)
    message: str = Field(..., min_length=1)
    type: str = Field(default="info")  # alert, warning, info, tip, achievement, reminder, recommendation
    priority: str = Field(default="medium")  # low, medium, high, critical
    image_url: Optional[str] = Field(None, max_length=500)
    action_url: Optional[str] = Field(None, max_length=500)
    data: Optional[Dict[str, Any]] = None
    category: Optional[str] = Field(None, max_length=50)
    group_key: Optional[str] = Field(None, max_length=100)
    scheduled_for: Optional[datetime] = None
    expires_at: Optional[datetime] = None


class NotificationResponse(UserOwnedResponseSchema):
    """Schema for notification response"""
    # id, user_id, created_at, updated_at inherited from UserOwnedResponseSchema
    title: str
    message: str
    type: str
    priority: str
    image_url: Optional[str] = None
    action_url: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    status: str
    channel: Optional[str] = None
    is_read: bool
    read_at: Optional[datetime] = None
    scheduled_for: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    error_message: Optional[str] = None
    updated_at: datetime  # Override to make non-optional
    expires_at: Optional[datetime] = None
    category: Optional[str] = None
    group_key: Optional[str] = None


class NotificationListResponse(BaseModel):
    """Schema for list of notifications"""
    notifications: list[NotificationResponse]
    total: int
    unread_count: int
    has_more: bool


class NotificationMarkReadRequest(BaseModel):
    """Schema for marking notification as read"""
    notification_id: UUID


class NotificationPreferencesUpdate(BaseModel):
    """Schema for updating notification preferences"""
    push_enabled: bool = True
    email_enabled: bool = True
    budget_alerts: bool = True
    goal_updates: bool = True
    daily_reminders: bool = True
    ai_recommendations: bool = True
    transaction_alerts: bool = True
    achievement_notifications: bool = True


class NotificationPreferencesResponse(BaseModel):
    """Schema for notification preferences response"""
    push_enabled: bool
    email_enabled: bool
    budget_alerts: bool
    goal_updates: bool
    daily_reminders: bool
    ai_recommendations: bool
    transaction_alerts: bool
    achievement_notifications: bool

    class Config:
        from_attributes = True

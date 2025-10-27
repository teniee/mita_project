from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.session import get_async_db, get_db
from app.db.models import PushToken, UserPreference
from app.services.notification_log_service import log_notification
from app.services.notification_service import NotificationService
from app.services.push_service import send_apns_notification, send_push_notification
from app.utils.email_utils import send_reminder_email
from app.utils.response_wrapper import success_response

from .schemas import (
    NotificationCreate,
    NotificationListResponse,
    NotificationMarkReadRequest,
    NotificationPreferencesResponse,
    NotificationPreferencesUpdate,
    NotificationResponse,
    NotificationTest,
    TokenIn,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.post("/register-token")
async def register_token(
    data: TokenIn,
    db: Session = Depends(get_db),  # noqa: B008
    user=Depends(get_current_user),  # noqa: B008
):
    token = PushToken(user_id=user.id, token=data.token, platform=data.platform)
    db.add(token)
    db.commit()
    db.refresh(token)
    return success_response({"id": str(token.id), "token": token.token})


@router.post("/test")
async def send_test_notification(
    payload: NotificationTest,
    db: Session = Depends(get_db),  # noqa: B008
    user=Depends(get_current_user),  # noqa: B008
):
    token = payload.token
    platform = payload.platform
    if not token:
        record = (
            db.query(PushToken)
            .filter(PushToken.user_id == user.id)
            .order_by(PushToken.created_at.desc())
            .first()
        )
        if record:
            token = record.token
            platform = record.platform

    if token:
        try:
            if platform == "apns":
                send_apns_notification(
                    user_id=user.id, message=payload.message, token=token, db=db
                )
            else:
                send_push_notification(
                    user_id=user.id, message=payload.message, token=token, db=db
                )
        except Exception:
            log_notification(
                db,
                user_id=user.id,
                channel=platform or "push",
                message=payload.message,
                success=False,
            )

    email = payload.email or user.email
    try:
        send_reminder_email(
            email,
            "Mita Notification",
            payload.message,
            user_id=str(user.id),
            db=db,
        )
    except Exception:
        pass

    return success_response({"sent": True})


# NEW ENDPOINTS for mobile app device management

@router.post("/register-device")
async def register_device(
    device_data: dict,
    db: Session = Depends(get_db),  # noqa: B008
    user=Depends(get_current_user),  # noqa: B008
):
    """Register device for push notifications"""
    device_id = device_data.get("device_id")
    device_token = device_data.get("token")
    platform = device_data.get("platform", "fcm")
    device_name = device_data.get("device_name")

    # Check if device already registered
    existing = db.query(PushToken).filter(
        PushToken.user_id == user.id,
        PushToken.token == device_token
    ).first()

    if existing:
        # Update existing
        existing.platform = platform
        db.commit()
        return success_response({
            "device_id": device_id,
            "status": "updated",
            "token_id": str(existing.id)
        })

    # Create new device registration
    token = PushToken(
        user_id=user.id,
        token=device_token,
        platform=platform
    )
    db.add(token)
    db.commit()
    db.refresh(token)

    return success_response({
        "device_id": device_id,
        "status": "registered",
        "token_id": str(token.id)
    })


@router.post("/unregister-device")
async def unregister_device(
    device_data: dict,
    db: Session = Depends(get_db),  # noqa: B008
    user=Depends(get_current_user),  # noqa: B008
):
    """Unregister device from push notifications"""
    device_token = device_data.get("token")

    if device_token:
        db.query(PushToken).filter(
            PushToken.user_id == user.id,
            PushToken.token == device_token
        ).delete()
        db.commit()

    return success_response({
        "status": "unregistered",
        "token": device_token
    })


@router.post("/update-device")
async def update_device(
    device_data: dict,
    db: Session = Depends(get_db),  # noqa: B008
    user=Depends(get_current_user),  # noqa: B008
):
    """Update device registration info"""
    old_token = device_data.get("old_token")
    new_token = device_data.get("new_token")
    platform = device_data.get("platform")

    if old_token and new_token:
        # Find and update existing token
        existing = db.query(PushToken).filter(
            PushToken.user_id == user.id,
            PushToken.token == old_token
        ).first()

        if existing:
            existing.token = new_token
            if platform:
                existing.platform = platform
            db.commit()
            return success_response({
                "status": "updated",
                "token_id": str(existing.id)
            })

    # If not found, create new
    token = PushToken(
        user_id=user.id,
        token=new_token,
        platform=platform or "fcm"
    )
    db.add(token)
    db.commit()
    db.refresh(token)

    return success_response({
        "status": "created",
        "token_id": str(token.id)
    })


# NEW ENDPOINTS for notification management

@router.get("/list", response_model=NotificationListResponse)
async def get_notifications(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    unread_only: bool = Query(False),
    type: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_async_db),
    user=Depends(get_current_user),
):
    """
    Get list of notifications for current user with optional filters

    Query Parameters:
    - limit: Max number of notifications (1-100, default 50)
    - offset: Offset for pagination (default 0)
    - unread_only: Only return unread notifications (default false)
    - type: Filter by notification type
    - priority: Filter by priority level
    - category: Filter by category
    """
    service = NotificationService(db)

    # Get notifications
    notifications = await service.get_user_notifications(
        user_id=user.id,
        limit=limit,
        offset=offset,
        unread_only=unread_only,
        notification_type=type,
        priority=priority,
        category=category,
    )

    # Get unread count
    unread_count = await service.get_unread_count(user.id)

    # Convert to response format
    notification_responses = [
        NotificationResponse.from_orm(notification) for notification in notifications
    ]

    return NotificationListResponse(
        notifications=notification_responses,
        total=len(notification_responses),
        unread_count=unread_count,
        has_more=len(notifications) == limit,
    )


@router.get("/{notification_id}", response_model=NotificationResponse)
async def get_notification(
    notification_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    user=Depends(get_current_user),
):
    """Get a specific notification by ID"""
    service = NotificationService(db)

    notification = await service.get_notification_by_id(notification_id, user.id)

    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    return NotificationResponse.from_orm(notification)


@router.post("/create", response_model=NotificationResponse)
async def create_notification(
    payload: NotificationCreate,
    db: AsyncSession = Depends(get_async_db),
    user=Depends(get_current_user),
):
    """Create a new notification (mainly for admin/testing)"""
    service = NotificationService(db)

    notification = await service.create_notification(
        user_id=user.id,
        title=payload.title,
        message=payload.message,
        type=payload.type,
        priority=payload.priority,
        image_url=payload.image_url,
        action_url=payload.action_url,
        data=payload.data,
        category=payload.category,
        group_key=payload.group_key,
        scheduled_for=payload.scheduled_for,
        expires_at=payload.expires_at,
    )

    return NotificationResponse.from_orm(notification)


@router.post("/{notification_id}/mark-read", response_model=NotificationResponse)
async def mark_notification_read(
    notification_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    user=Depends(get_current_user),
):
    """Mark a notification as read"""
    service = NotificationService(db)

    notification = await service.mark_as_read(notification_id, user.id)

    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    return NotificationResponse.from_orm(notification)


@router.post("/mark-all-read")
async def mark_all_notifications_read(
    db: AsyncSession = Depends(get_async_db),
    user=Depends(get_current_user),
):
    """Mark all notifications as read for current user"""
    service = NotificationService(db)

    count = await service.mark_all_as_read(user.id)

    return success_response({
        "marked_read": count,
        "message": f"Marked {count} notifications as read"
    })


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    user=Depends(get_current_user),
):
    """Delete a notification"""
    service = NotificationService(db)

    success = await service.delete_notification(notification_id, user.id)

    if not success:
        raise HTTPException(status_code=404, detail="Notification not found")

    return success_response({
        "deleted": True,
        "notification_id": str(notification_id)
    })


@router.get("/unread-count")
async def get_unread_count(
    db: AsyncSession = Depends(get_async_db),
    user=Depends(get_current_user),
):
    """Get count of unread notifications"""
    service = NotificationService(db)

    count = await service.get_unread_count(user.id)

    return success_response({
        "unread_count": count
    })


@router.get("/preferences", response_model=NotificationPreferencesResponse)
async def get_notification_preferences(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Get notification preferences for current user"""
    # Get or create user preferences
    prefs = db.query(UserPreference).filter(UserPreference.user_id == user.id).first()

    if not prefs:
        prefs = UserPreference(user_id=user.id)
        db.add(prefs)
        db.commit()
        db.refresh(prefs)

    return NotificationPreferencesResponse(
        push_enabled=getattr(prefs, 'push_enabled', True),
        email_enabled=getattr(prefs, 'email_enabled', True),
        budget_alerts=getattr(prefs, 'budget_alerts', True),
        goal_updates=getattr(prefs, 'goal_updates', True),
        daily_reminders=getattr(prefs, 'daily_reminders', True),
        ai_recommendations=getattr(prefs, 'ai_recommendations', True),
        transaction_alerts=getattr(prefs, 'transaction_alerts', True),
        achievement_notifications=getattr(prefs, 'achievement_notifications', True),
    )


@router.put("/preferences", response_model=NotificationPreferencesResponse)
async def update_notification_preferences(
    payload: NotificationPreferencesUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Update notification preferences for current user"""
    # Get or create user preferences
    prefs = db.query(UserPreference).filter(UserPreference.user_id == user.id).first()

    if not prefs:
        prefs = UserPreference(user_id=user.id)
        db.add(prefs)

    # Update preferences
    for key, value in payload.dict().items():
        setattr(prefs, key, value)

    db.commit()
    db.refresh(prefs)

    return NotificationPreferencesResponse(
        push_enabled=prefs.push_enabled,
        email_enabled=prefs.email_enabled,
        budget_alerts=prefs.budget_alerts,
        goal_updates=prefs.goal_updates,
        daily_reminders=prefs.daily_reminders,
        ai_recommendations=prefs.ai_recommendations,
        transaction_alerts=prefs.transaction_alerts,
        achievement_notifications=prefs.achievement_notifications,
    )

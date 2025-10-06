from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.session import get_db
from app.db.models import PushToken
from app.services.notification_log_service import log_notification
from app.services.push_service import send_apns_notification, send_push_notification
from app.utils.email_utils import send_reminder_email
from app.utils.response_wrapper import success_response

from .schemas import NotificationTest, TokenIn

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

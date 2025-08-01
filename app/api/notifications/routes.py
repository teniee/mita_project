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

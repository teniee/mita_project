import logging
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.session import get_db
from app.db.models import PushToken
from app.services.push_service import send_push_notification
from app.utils.email_utils import send_reminder_email
from app.utils.response_wrapper import success_response

from .schemas import TokenIn, NotificationTest

router = APIRouter(prefix="/notifications", tags=["notifications"])
logger = logging.getLogger(__name__)


@router.post("/register-token")
async def register_token(
    data: TokenIn,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    token = PushToken(user_id=user.id, token=data.token)
    db.add(token)
    db.commit()
    db.refresh(token)
    return success_response({"id": str(token.id), "token": token.token})


@router.post("/test")
async def send_test_notification(
    payload: NotificationTest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    token = payload.token
    if not token:
        record = (
            db.query(PushToken)
            .filter(PushToken.user_id == user.id)
            .order_by(PushToken.created_at.desc())
            .first()
        )
        token = record.token if record else None

    if token:
        try:
            send_push_notification(user_id=user.id, message=payload.message, token=token)
        except Exception as e:  # pragma: no cover - log and continue
            logger.warning("Push notification failed: %s", e)

    email = payload.email or user.email
    try:
        send_reminder_email(email, "Mita Notification", payload.message)
    except Exception as e:  # pragma: no cover - log and continue
        logger.warning("Reminder email failed: %s", e)

    return success_response({"sent": True})

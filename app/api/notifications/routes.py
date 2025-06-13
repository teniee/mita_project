from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.session import get_db
from app.db.models import PushToken
from app.services.email_service import send_email
from app.services.push_service import send_push_notification
from app.utils.response_wrapper import success_response

router = APIRouter(prefix="/notifications", tags=["notifications"])


class TokenIn(BaseModel):
    token: str


class EmailIn(BaseModel):
    to_email: str
    subject: str
    body: str


@router.post("/token")
def register_token(
    data: TokenIn,
    user=Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    db.add(PushToken(user_id=user.id, token=data.token))
    db.commit()
    return success_response({"status": "registered"})


@router.post("/push")
def send_push(
    data: TokenIn,
    user=Depends(get_current_user),  # noqa: B008
):
    resp = send_push_notification(
        user_id=user.id,
        message="Test",
        token=data.token,
    )
    return success_response(resp)


@router.post("/email")
def send_email_endpoint(
    data: EmailIn,
    user=Depends(get_current_user),  # noqa: B008
):
    send_email(data.to_email, data.subject, data.body)
    return success_response({"status": "sent"})

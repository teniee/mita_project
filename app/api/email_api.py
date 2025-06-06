from fastapi import APIRouter
from pydantic import BaseModel, EmailStr

from app.services.email_service import send_email
from app.utils.response_wrapper import success_response

router = APIRouter(prefix="/email", tags=["email"])


class EmailRequest(BaseModel):
    to: EmailStr
    subject: str
    body: str


@router.post("/send")
async def send_email_endpoint(payload: EmailRequest):
    result = send_email(payload.to, payload.subject, payload.body)
    return success_response(result)

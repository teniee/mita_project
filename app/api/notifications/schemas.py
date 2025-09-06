from typing import Optional
from pydantic import BaseModel, EmailStr


class TokenIn(BaseModel):
    token: str
    platform: str = "fcm"


class NotificationTest(BaseModel):
    message: str
    token: Optional[str] = None
    email: Optional[EmailStr] = None
    platform: Optional[str] = None

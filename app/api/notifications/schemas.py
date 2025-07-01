from pydantic import BaseModel, EmailStr

class TokenIn(BaseModel):
    token: str
    platform: str = "fcm"

class NotificationTest(BaseModel):
    message: str
    token: str | None = None
    email: EmailStr | None = None
    platform: str | None = None

from pydantic import BaseModel, EmailStr


class TokenIn(BaseModel):
    token: str


class NotificationTest(BaseModel):
    message: str
    token: str | None = None
    email: EmailStr | None = None

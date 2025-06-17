from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr


class UserProfileOut(BaseModel):
    id: str
    email: EmailStr
    country: str
    created_at: datetime
    timezone: str
    is_premium: bool
    premium_until: Optional[datetime] = None


class UserUpdateIn(BaseModel):
    email: Optional[EmailStr] = None
    country: Optional[str] = None
    timezone: Optional[str] = None

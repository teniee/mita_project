
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class UserProfileOut(BaseModel):
    id: str
    email: EmailStr
    country: str
    created_at: datetime

class UserUpdateIn(BaseModel):
    email: Optional[EmailStr] = None
    country: Optional[str] = None

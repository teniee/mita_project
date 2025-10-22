from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr


class UserProfileOut(BaseModel):
    id: str
    email: EmailStr
    country: str
    created_at: datetime
    timezone: str
    # Profile fields
    name: Optional[str] = None
    income: float = 0.0
    savings_goal: float = 0.0
    budget_method: str = "50/30/20 Rule"
    currency: str = "USD"
    region: Optional[str] = None
    # Preferences
    notifications_enabled: bool = True
    dark_mode_enabled: bool = False
    # Status
    has_onboarded: bool = False
    email_verified: bool = False
    # UI fields (for mobile app compatibility)
    member_since: Optional[str] = None
    profile_completion: Optional[int] = None
    verified_email: Optional[bool] = None


class UserUpdateIn(BaseModel):
    email: Optional[EmailStr] = None
    country: Optional[str] = None
    timezone: Optional[str] = None
    # Profile fields
    name: Optional[str] = None
    income: Optional[float] = None
    savings_goal: Optional[float] = None
    budget_method: Optional[str] = None
    currency: Optional[str] = None
    region: Optional[str] = None
    # Preferences
    notifications_enabled: Optional[bool] = None
    dark_mode_enabled: Optional[bool] = None

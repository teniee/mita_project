from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime


class WaitlistJoinRequest(BaseModel):
    email: EmailStr
    ref_code: Optional[str] = Field(None, max_length=12, description="Referral code from a friend")


class WaitlistJoinResponse(BaseModel):
    email: str
    position: int
    effective_position: int   # position minus boost
    ref_code: str             # user's own referral code
    referral_link: str
    referral_count: int
    total_signups: int
    message: str


class WaitlistStatusResponse(BaseModel):
    email: str
    position: int
    effective_position: int
    ref_code: str
    referral_link: str
    referral_count: int
    position_boost: int
    confirmed: bool
    total_signups: int
    joined_at: datetime


class WaitlistConfirmResponse(BaseModel):
    email: str
    confirmed: bool
    message: str

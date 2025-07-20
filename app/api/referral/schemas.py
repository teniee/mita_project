from typing import Optional

from pydantic import BaseModel


class ReferralInput(BaseModel):
    pass


class ReferralResult(BaseModel):
    eligible: Optional[bool] = None
    reward: Optional[str] = None
    activation: Optional[str] = None
    claimable: Optional[bool] = None
    status: Optional[str] = None
    new_premium_until: Optional[str] = None
    reason: Optional[str] = None

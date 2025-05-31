
from pydantic import BaseModel

class ReferralRequest(BaseModel):
    user_id: str

class ReferralClaimRequest(BaseModel):
    user_id: str
    code: str

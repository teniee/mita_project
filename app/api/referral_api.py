from fastapi import APIRouter
from pydantic import BaseModel
from app.services.core.api.referral_engine import check_referral_eligibility
from app.utils.response_wrapper import success_response

router = APIRouter(prefix="/referral", tags=["referral"])

class ReferralRequest(BaseModel):
    invited_users: int
    active_referrals: int

@router.post("/eligibility")
async def referral_eligibility(payload: ReferralRequest):
    eligible = check_referral_eligibility(payload.invited_users, payload.active_referrals)
    return success_response({"eligible": eligible})
from app.utils.response_wrapper import success_response

from fastapi import APIRouter, HTTPException
from app.schemas.referral import ReferralRequest, ReferralClaimRequest
from app.services.core.api.referral_engine import evaluate_referral_eligibility, apply_referral_claim

router = APIRouter()

@router.post("/evaluate")
def evaluate_referral(request: ReferralRequest):
    return success_response({"eligible": evaluate_referral_eligibility(request.user_id)})

@router.post("/claim")
def claim_referral(request: ReferralClaimRequest):
    return apply_referral_claim(request.user_id, request.code)
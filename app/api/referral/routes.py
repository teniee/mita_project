from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.referral.schemas import ReferralInput, ReferralResult
from app.api.referral.services import check_referral, claim_referral
from app.core.db import get_db
from app.utils.response_wrapper import success_response

router = APIRouter(prefix="/referral", tags=["referral"])


@router.post("/eligibility", response_model=ReferralResult)
async def eligibility(data: ReferralInput, db: AsyncSession = Depends(get_db)):
    result = await check_referral(data.user_id, db)
    return success_response(result)


@router.post("/claim", response_model=ReferralResult)
async def claim(data: ReferralInput, db: AsyncSession = Depends(get_db)):
    result = await claim_referral(data.user_id, db)
    return success_response(result)

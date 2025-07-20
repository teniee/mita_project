from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.models import User
from app.services.core.api.referral_engine import (
    apply_referral_claim,
    evaluate_referral_eligibility,
)


async def check_referral(user_id: str, db: AsyncSession):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    referred_result = await db.execute(select(User).where(User.referred_by == user_id))
    referred_users = referred_result.scalars().all()

    referred_payload = [{"is_premium": u.is_premium} for u in referred_users]
    user_payload = {
        "id": user.id,
        "premium_until": user.premium_until.isoformat() if user.premium_until else None,
        "referral_reward_used": user.referral_reward_used,
    }

    return evaluate_referral_eligibility(user_payload, referred_payload)


async def claim_referral(user_id: str, db: AsyncSession):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    if user.referral_reward_used:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Reward already claimed"
        )

    user_payload = {
        "id": user.id,
        "premium_until": user.premium_until.isoformat() if user.premium_until else None,
        "referral_reward_used": False,
    }

    result_data = apply_referral_claim(user_payload)

    user.premium_until = result_data["new_premium_until"]
    user.referral_reward_used = True
    await db.commit()

    return result_data

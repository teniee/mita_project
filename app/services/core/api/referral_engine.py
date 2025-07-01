from typing import Any
from typing import Dict, List, Optional
from datetime import datetime, timedelta

def evaluate_referral_eligibility(user: Dict, referred_users: List[Dict]) -> Dict[str, Any]:
    """
    Checks if a user is eligible for a referral reward.
    Conditions:
    - Must have 3+ referred users who are premium
    - Reward must be claimed manually
    - Applies to annual plan only
    """
    if not referred_users or len(referred_users) < 3:
        return {"eligible": False, "reason": "Not enough referrals"}

    premium_count = sum(1 for u in referred_users if u.get("is_premium"))
    if premium_count < 3:
        return {"eligible": False, "reason": "Less than 3 referred users are premium"}

    return {
        "eligible": True,
        "reward": "-20%_annual",
        "activation": "manual",
        "claimable": True
    }

def apply_referral_claim(user: Dict) -> Dict[str, Any]:
    """
    Applies referral reward to a user's premium status.
    Must be called manually when user activates reward.
    """
    today = datetime.today().date()
    premium_until = datetime.strptime(user.get("premium_until", today.isoformat()), "%Y-%m-%d").date()
    extended_until = premium_until + timedelta(days=365)
    user["premium_until"] = extended_until.isoformat()
    user["referral_reward_used"] = True
    return {
        "status": "success",
        "new_premium_until": user["premium_until"]
    }

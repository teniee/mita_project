from datetime import datetime
from typing import List, Dict, Any
from app.engine.challenge_engine import check_monthly_challenge_eligibility


def auto_run_challenge_streak(calendar: List[Dict], user_id: str, log_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Automatically checks streak eligibility daily.
    log_data example: {"last_claimed": "2025-01-01"}
    """
    today = datetime.today().strftime("%Y-%m-%d")
    result = check_monthly_challenge_eligibility(calendar, today, log_data)

    return {
        "user_id": user_id,
        "date": today,
        "streak_eligible": result.get("eligible", False),
        "claimable": result.get("claimable", False),
        "reward": result.get("reward") if result.get("eligible") else None,
        "streak_days": result.get("streak_days", 0)
    }

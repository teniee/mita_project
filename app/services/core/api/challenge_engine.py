from typing import Any
from typing import List, Dict, Any
from datetime import datetime, timedelta

def check_monthly_challenge_eligibility(calendar: List[Dict], today_date: str,
                                        challenge_log: Dict[str, Any]) -> Dict[str, Any]:
    """
    Returns eligibility for 30-day no-overspend challenge.
    challenge_log = {
        "last_claimed": "2024-12-01"
    }
    """
    # Parse current date
    today = datetime.strptime(today_date, "%Y-%m-%d").date()

    # Cooldown check
    last_claimed = challenge_log.get("last_claimed")
    if last_claimed:
        last_date = datetime.strptime(last_claimed, "%Y-%m-%d").date()
        if (today - last_date).days < 30:
            return {
                "eligible": False,
                "reason": f"Cooldown active until {(last_date + timedelta(days=30)).isoformat()}"
            }

    # Count streak days (terminate streak on first overspent)
    streak = 0
    for day in calendar:
        if day["date"] > today_date:
            break
        if "overspent" in day.get("status", {}).values():
            streak = 0
            break
        streak += 1

    if streak >= 30:
        return {
            "eligible": True,
            "streak_days": streak,
            "reward": "-20%_annual",
            "activation": "manual",
            "claimable": True
        }
    return {
        "eligible": False,
        "streak_days": streak,
        "claimable": False
    }

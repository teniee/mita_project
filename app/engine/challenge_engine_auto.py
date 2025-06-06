from datetime import datetime
from typing import Any, Dict, List

from app.engine.challenge_engine import check_monthly_challenge_eligibility


class ChallengeEngine:
    """Simple challenge generator used by progress trackers."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config or {}

    def generate_challenges(self) -> List[Dict[str, Any]]:
        categories = self.config.get("categories") or ["food"]
        default_limit = self.config.get("default_limit", 100)
        limits = self.config.get("limits", {})
        duration = self.config.get("duration", 30)

        return [
            {
                "category": cat,
                "limit": limits.get(cat, default_limit),
                "duration": duration,
            }
            for cat in categories
        ]


def auto_run_challenge_streak(
    calendar: List[Dict], user_id: str, log_data: Dict[str, Any]
) -> Dict[str, Any]:
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
        "streak_days": result.get("streak_days", 0),
    }

from app.engine.analytics_engine import AnalyticsEngine
from app.engine.calendar_store import get_calendar_for_user

analytics = AnalyticsEngine()
# challenge_tracker.py - tracks challenge performance for current month


class ChallengeTracker:
    def __init__(self, challenges):
        self.challenges = challenges or []

    def evaluate_challenge(
        self, user_id: str, year: int, month: int, profile: dict = None
    ):
        cal = get_calendar_for_user(user_id, year, month)
        days = cal.values() if isinstance(cal, dict) else cal
        results = []

        for challenge in self.challenges:
            cat = challenge["category"]
            limit = challenge["limit"]
            duration = challenge.get("duration", 30)
            total = 0
            days = 0

            for day_data in days:
                day_actual = day_data.get(
                    "actual_spent",
                    day_data.get("actual", {}),
                )
                if cat in day_actual:
                    total += day_actual.get(cat, 0)
                    days += 1

            results.append(
                {
                    "category": cat,
                    "limit": limit,
                    "spent": round(total, 2),
                    "completed": total <= limit and days >= duration,
                }
            )

        if profile:
            for r in results:
                analytics.log_behavior(
                    user_id,
                    profile.get("region", "US-CA"),
                    profile.get("cohort", "unknown"),
                    profile.get("behavior", "neutral"),
                    r["completed"],
                    False,
                )
        return results

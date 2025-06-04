from app.engine.analytics_engine import AnalyticsEngine
analytics = AnalyticsEngine()
### challenge_tracker.py — tracks challenge performance for current month

# [REMOVED] from app.engine.calendar_store import get_calendar_for_user


class ChallengeTracker:
    def __init__(self, challenges):
        self.challenges = challenges or []

    def evaluate_challenge(self, user_id: str, year: int, month: int, profile: dict = None):
# [REMOVED]         cal = get_calendar_for_user(user_id, year, month)
        results = []

        for challenge in self.challenges:
            cat = challenge["category"]
            limit = challenge["limit"]
            duration = challenge.get("duration", 30)
            total = 0
            days = 0

            for day, data in cal.items():
                if cat in data:
                    total += data[cat]
                    days += 1

            results.append({
                "category": cat,
                "limit": limit,
                "spent": round(total, 2),
                "completed": total <= limit and days >= duration
            })

        if profile:
            for r in results:
                analytics.log_behavior(
                    user_id,
                    profile.get("region", "US-CA"),
                    profile.get("cohort", "unknown"),
                    profile.get("behavior", "neutral"),
                    r["completed"],
                    False
                )
        return results

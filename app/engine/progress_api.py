# progress_api.py - progress + real challenge impact for Progress Tab

from challenge_tracker import ChallengeTracker

from app.services.calendar_service_real import get_calendar_for_user
from app.engine.challenge_engine_auto import ChallengeEngine
from app.engine.locale_utils import format_currency
from app.engine.progress_tracker import ProgressTracker

tracker = ProgressTracker()
engine = ChallengeEngine({"categories": []})


def get_progress_data(
    user_id: str,
    year: int,
    month: int,
) -> dict:
    progress = tracker.get_month_data(user_id, year, month)
    cal = get_calendar_for_user(user_id, year, month)
    days = cal.values() if isinstance(cal, dict) else cal
    challenges = engine.generate_challenges()
    tracker_v2 = ChallengeTracker(challenges)
    challenge_results = tracker_v2.evaluate_challenge(user_id, year, month)

    saved_from_challenges = 0
    completed = []

    for result in challenge_results:
        if result["completed"]:
            completed.append(result)
            cat = result["category"]
            planned_total = sum(
                day.get("planned_budget", day.get("planned", {})).get(cat, 0)
                for day in days
            )
            actual_total = sum(
                day.get("actual_spent", day.get("actual", {})).get(cat, 0)
                for day in days
            )
            saved_from_challenges += round(planned_total - actual_total, 2)

    currency = "USD"
    locale = "en_US"

    return {
        "spent": (
            format_currency(progress.get("spent", 0), currency, locale)
            if progress
            else None
        ),
        "saved": (
            format_currency(progress.get("saved", 0), currency, locale)
            if progress
            else None
        ),
        "challenge_completed": len(completed),
        "challenge_impact_actual": format_currency(
            saved_from_challenges, currency, locale
        ),
        "challenge_breakdown": challenge_results,
    }

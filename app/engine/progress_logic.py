from app.engine.progress_tracker import ProgressTracker
# [REMOVED] from app.engine.calendar_store import get_calendar_for_user
from app.engine.challenge_tracker import ChallengeTracker
from app.engine.locale_utils import format_currency

tracker = ProgressTracker()

def get_progress_data(user_id: str, year: int, month: int, config: dict) -> dict:
    progress = tracker.get_month_data(user_id, year, month)
# [REMOVED]     cal = get_calendar_for_user(user_id, year, month)

    # Челленджи пока пустые — логика генерации будет позже
    tracker_v2 = ChallengeTracker([])
    challenge_results = tracker_v2.evaluate_challenge(user_id, year, month)

    saved_from_challenges = 0
    completed = []

    for result in challenge_results:
        if result.get("completed"):
            completed.append(result)
            cat = result["category"]
            planned_total = sum(day.get("planned", {}).get(cat, 0) for day in cal)
            actual_total = sum(day.get("actual", {}).get(cat, 0) for day in cal)
            saved_from_challenges += round(planned_total - actual_total, 2)

    currency = config.get("currency", "USD")
    locale = config.get("locale", "en_US")

    return {
        "spent": format_currency(progress.get("spent", 0), currency, locale) if progress else None,
        "saved": format_currency(progress.get("saved", 0), currency, locale) if progress else None,
        "challenge_completed": len(completed),
        "challenge_impact_actual": format_currency(saved_from_challenges, currency, locale),
        "challenge_breakdown": challenge_results
    }

### ai_feedback_generator.py — builds natural feedback based on user behavior

from app.engine.progress_tracker import ProgressTracker
from challenge_tracker import ChallengeTracker
from app.engine.challenge_engine_auto import ChallengeEngine
from spending_pattern_extractor import extract_patterns
from mood_store import get_mood
from cohort_cluster_engine import CohortClusterEngine
from app.engine.locale_utils import format_currency
from datetime import date


def generate_feedback(user_id: str, config: dict, year: int, month: int, calendar: dict) -> str:
    progress = ProgressTracker().get_month_data(user_id, year, month) or {}
    challenges = ChallengeEngine(config).generate_challenges()
    challenge_results = ChallengeTracker(challenges).evaluate_challenge(user_id, year, month)
    patterns = extract_patterns(user_id, year, month)["patterns"]
    cluster = CohortClusterEngine()
    cluster.fit({user_id: {"calendar": calendar}})
    cluster_id = cluster.get_label(user_id)
    today = date.today().isoformat()
    mood = get_mood(user_id, today)

    spent = progress.get("spent", 0)
    saved = progress.get("saved", 0)
    completed = sum(1 for c in challenge_results if c["completed"])
    saving_goal = config.get("savings_target")
    currency = config.get("currency", "USD")
    locale = config.get("locale", "en_US")

    parts = []

    if saving_goal:
        if saved >= saving_goal:
            parts.append("You've already hit your goal. Well played.")
        else:
            gap = round(saving_goal - saved, 2)
            parts.append(f"You're {format_currency(gap, currency, locale)} away from your goal — stay focused.")

    parts.append(f"You've saved {format_currency(saved, currency, locale)} this month and spent {format_currency(spent, currency, locale)}.")

    if completed:
        parts.append(f"You completed {completed} challenges. Keep stacking wins.")

    if mood:
        parts.append(f"You're feeling {mood} today. Let that guide your next move.")

    if patterns:
        parts.append(f"Behavior flags: {', '.join(patterns)}.")

    parts.append(f"You're currently in cluster {cluster_id}.")

    return " ".join(parts)

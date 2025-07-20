### assistant_logic_router.py — routes logic for behavioral assistant responses

from datetime import date

from ai_feedback_generator import generate_feedback
from mood_store import get_mood

from app.engine.progress_tracker import ProgressTracker


def get_assistant_response(
    user_id: str, config: dict, year: int, month: int, calendar: dict
) -> str:
    today = date.today()
    mood = get_mood(user_id, today.isoformat())
    progress = ProgressTracker().get_month_data(user_id, year, month)
    feedback = generate_feedback(user_id, config, year, month, calendar)

    if not progress:
        return "Let's start building your first budget."  # baseline

    if mood in ["stressed", "anxious"]:
        return "Looks like it's a rough day. Want to slow spending today?"

    return feedback

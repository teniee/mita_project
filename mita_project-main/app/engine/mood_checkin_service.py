"""Service for handling user mood submissions."""

from datetime import datetime

from app.engine.mood_store import save_mood


def save_user_mood(
    user_id: str,
    mood: str,
    timestamp: str | None = None,
) -> None:
    """Persist user mood for the given date."""
    date_str = timestamp or datetime.utcnow().date().isoformat()
    save_mood(user_id, date_str, mood)


def submit_mood(user_id: str, mood: str):
    date_str = datetime.utcnow().date().isoformat()
    save_mood(user_id, date_str, mood)
    return {"status": "ok", "date": date_str, "mood": mood}

### mood_checkin_service.py — handle mood input for tracking and assistant context

from mood_store import save_mood
from datetime import datetime


def submit_mood(user_id: str, mood: str):
    today = datetime.today().date().isoformat()
    save_mood(user_id, today, mood)
    return {"status": "ok", "date": today, "mood": mood}
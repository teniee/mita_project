### mood_store.py — stores per-day user mood ratings for behavioral context

mood_db = {}

def save_mood(user_id: str, date: str, mood: str):
    if user_id not in mood_db:
        mood_db[user_id] = {}
    mood_db[user_id][date] = mood

def get_mood(user_id: str, date: str):
    return mood_db.get(user_id, {}).get(date)
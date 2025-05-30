### day_view_api.py — returns single-day view for UI consumption

# [REMOVED] from app.engine.calendar_store import get_calendar_for_user
from datetime import date


def get_day_view(user_id: str, year: int, month: int, day: int):
# [REMOVED]     cal = get_calendar_for_user(user_id, year, month)
    if not cal:
        return {"error": "calendar not found"}

    day_key = f"{year:04d}-{month:02d}-{day:02d}"
    day_data = cal.get(day_key)
    if not day_data:
        return {"error": "day not found"}

    return {
        "date": day_key,
        "day": day_data
    }
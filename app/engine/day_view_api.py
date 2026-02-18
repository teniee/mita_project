# day_view_api.py - returns single-day view for UI consumption

from app.services.calendar_service_real import get_calendar_for_user


def get_day_view(user_id: str, year: int, month: int, day: int):
    cal = get_calendar_for_user(user_id, year, month)
    if not cal:
        return {"error": "calendar not found"}

    day_key = f"{year:04d}-{month:02d}-{day:02d}"
    day_data = (
        cal.get(day_key)
        if isinstance(cal, dict)
        else next(
            (d for d in cal if d.get("date") == day_key),
            None,
        )
    )
    if not day_data:
        return {"error": "day not found"}

    return {
        "date": day_key,
        "day": day_data,
    }

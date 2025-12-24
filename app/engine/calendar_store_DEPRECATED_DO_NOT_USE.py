"""
⚠️ DEPRECATED - DO NOT USE ⚠️

This file contains an IN-MEMORY ONLY calendar store that does NOT persist to database.
It was used for early development/testing and should NOT be used in production code.

For production calendar storage, use:
- app/services/calendar_service_real.py - Saves to PostgreSQL DailyPlan table

This file is kept for reference only and will be removed in a future cleanup.
"""
from typing import Dict, List

# Simple in-memory calendar store used for development
# ⚠️ WARNING: Data stored here is LOST when the application restarts!
CALENDAR_DB: Dict[str, List[Dict]] = {}


def save_calendar(calendar_id: str, days: List[Dict]) -> Dict:
    CALENDAR_DB[calendar_id] = days
    return {"status": "saved", "calendar_id": calendar_id, "days": len(days)}


def get_calendar(calendar_id: str) -> List[Dict]:
    return CALENDAR_DB.get(calendar_id, [])


def update_calendar(calendar_id: str, updated_days: List[Dict]) -> Dict:
    if calendar_id in CALENDAR_DB:
        CALENDAR_DB[calendar_id] = updated_days
        return {"status": "updated", "calendar_id": calendar_id}
    return {"status": "not_found", "calendar_id": calendar_id}


def reset_calendar_store() -> None:
    CALENDAR_DB.clear()


def get_calendar_for_user(user_id: str, year: int, month: int) -> List[Dict]:
    calendar_id = f"{user_id}-{year}-{month:02d}"
    return get_calendar(calendar_id)


def save_calendar_for_user(
    user_id: str, year: int, month: int, calendar: List[Dict]
) -> Dict:
    calendar_id = f"{user_id}-{year}-{month:02d}"
    return save_calendar(calendar_id, calendar)

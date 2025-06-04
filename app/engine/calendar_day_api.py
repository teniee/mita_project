from fastapi import APIRouter, HTTPException, Body
from calendar_engine import CalendarEngine
from user_calendar_store import get_calendar_for_user, save_calendar_for_user, get_config_for_user

router = APIRouter()

@router.get("/calendar/day/{user_id}/{year}/{month}/{day}")
def get_day(user_id: str, year: int, month: int, day: int):
    calendar = get_calendar_for_user(user_id, year, month)
    if not calendar or day not in calendar:
        raise HTTPException(status_code=404, detail="Day not found")
    return calendar[day]

@router.post("/calendar/day/{user_id}/{year}/{month}/{day}/edit")
def edit_day(user_id: str, year: int, month: int, day: int, 
             updates: dict = Body(...)):
    calendar = get_calendar_for_user(user_id, year, month)
    if not calendar or day not in calendar:
        raise HTTPException(status_code=404, detail="Day not found")

    day_data = calendar[day]
    expenses = day_data.get("expenses", {})

    for category, value in updates.items():
        expenses[category] = round(float(value), 2)

    day_data["expenses"] = expenses
    day_data["total"] = round(sum(expenses.values()), 2)
    calendar[day] = day_data

    save_calendar_for_user(user_id, year, month, calendar)
    return {"status": "ok", "day": calendar[day]}
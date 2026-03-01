from datetime import date
from typing import Dict

from app.engine.calendar_engine_behavioral import build_calendar
from app.services.calendar_service_real import get_calendar_for_user, save_calendar_for_user


def generate_calendar(
    calendar_id: str, start_date: date, num_days: int, budget_plan: Dict[str, float]
):
    calendar_days = build_calendar(start_date, num_days, budget_plan)
    save_calendar_for_user(
        calendar_id, start_date.year, start_date.month, calendar_days
    )
    return calendar_days


def fetch_calendar(calendar_id: str, year: int, month: int):
    return get_calendar_for_user(calendar_id, year, month)


def get_day(calendar: dict, day: int):
    if day not in calendar:
        return None
    return calendar[day]


def update_day(calendar: dict, day: int, updates: Dict[str, float]):
    day_data = calendar.get(day)
    if not day_data:
        return None
    expenses = day_data.get("expenses", {})
    for category, value in updates.items():
        expenses[category] = round(float(value), 2)
    day_data["expenses"] = expenses
    day_data["total"] = round(sum(expenses.values()), 2)
    calendar[day] = day_data
    return calendar[day]


from app.engine.calendar_state_service import get_calendar_day_state


def fetch_day_state(user_id: str, year: int, month: int, day: int) -> dict:
    return get_calendar_day_state(user_id, year, month, day)


from app.engine.budget_redistributor import redistribute_budget


def redistribute_calendar_budget(calendar: dict, strategy: str = "balance") -> dict:
    return redistribute_budget(calendar, strategy)


from app.engine.budget_mode_shell_integration import get_shell_calendar


def generate_shell_calendar(user_id: str, shell_config: dict) -> dict:
    return get_shell_calendar(user_id, shell_config)

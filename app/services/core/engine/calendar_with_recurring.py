from app.services.core.engine.monthly_budget_engine import build_monthly_budget
from app.services.core.engine.recurring_expense_handler import inject_recurring_expenses


def build_calendar_with_recurring(
    user_answers: dict, year: int, month: int, db, user_id: int
) -> list:
    calendar = build_monthly_budget(user_answers, year, month)
    calendar = inject_recurring_expenses(db=db, user_id=user_id, calendar=calendar)
    return calendar

from app.engine.calendar_engine_behavioral import build_calendar
from app.services.calendar_service_real import save_calendar_for_user
from app.services.core.engine.budget_logic import generate_budget_from_answers
from app.core.session import get_db


def generate_and_save_calendar(user_id: int, answers: dict, db=None, year=2025, month=5):
    """
    Generates a detailed spending calendar from user onboarding answers
    and saves it to the database.
    """
    if db is None:
        db = next(get_db())

    budget_plan = generate_budget_from_answers(answers)

    calendar_config = {
        "user_id": user_id,
        "year": year,
        "month": month,
        "db": db,
        **answers,
        **budget_plan
    }

    calendar = build_calendar(calendar_config)
    save_calendar_for_user(db, user_id, calendar)

    return calendar

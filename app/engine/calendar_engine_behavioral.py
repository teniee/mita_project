from app.engine.calendar_behavior_logger import CalendarBehaviorLogger
from app.engine.goal_budget_engine import build_goal_budget
from app.services.core.engine.monthly_budget_engine import build_monthly_budget
# used by downstream logic: from app.db.models import RecurringExpense
from app.services.behavior_adapter import apply_behavioral_adjustments


calendar_logger = CalendarBehaviorLogger()

def build_calendar(config: dict) -> dict:
    """Generate a spending calendar based on behavioral patterns.

    Considers:
    - Social class
    - Category weights
    - Templates (fixed, spread, clustered)
    - Recurring expenses from the database

    Returns mapping: date -> category -> amount.
    """
    mode = config.get("mode", "default")
    year = config.get("year", 2025)
    month = config.get("month", 1)

    if mode == "goal":
        income = config["income"]
        fixed = config["fixed"]
        weights = config["weights"]
        goal = config.get("savings_target", 0)
        result = build_goal_budget(income, fixed, goal, weights)
    else:
        user_id = config.get("user_id")
        if not user_id:
            raise ValueError("Missing 'user_id' in config for behavioral calendar generation")

        config = apply_behavioral_adjustments(user_id=user_id, config=config, db=config.get('db'))
        result = build_monthly_budget(user_answers=config, year=year, month=month)

    return result

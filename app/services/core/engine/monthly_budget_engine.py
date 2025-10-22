import calendar
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Dict, List

from app.config.country_profiles_loader import COUNTRY_PROFILES
from app.services.core.behavior.behavioral_budget_allocator import (
    get_behavioral_allocation,
)
from app.services.core.engine.budget_logic import generate_budget_from_answers
from app.services.core.engine.calendar_engine import distribute_budget_over_days


def build_monthly_budget(user_answers: dict, year: int, month: int) -> List[Dict]:
    """
    Builds a behaviorally-adaptive, region-sensitive, goal-aware monthly budget plan.

    Args:
        user_answers (dict): Full questionnaire result from onboarding.
        year (int): Year for the budget plan.
        month (int): Month for the budget plan.

    Returns:
        List[Dict]: List of daily budgets with planned spending.
    """
    # Extract data
    region = user_answers.get("region", "US-CA")
    income = Decimal(str(user_answers.get("monthly_income", 3000))).quantize(
        Decimal("0.01")
    )

    # Get behavioral profile (weights, frequencies, etc.)
    profile = COUNTRY_PROFILES.get(region, {})
    fixed = user_answers.get("fixed_expenses", {})
    savings_goal = Decimal(
        str(user_answers.get("goals", {}).get("savings_goal_amount_per_month", 0))
    )

    # Validate budget feasibility
    fixed_total = sum(Decimal(str(v)) for v in fixed.values())
    discretionary = income - fixed_total - savings_goal
    if discretionary < 0:
        raise ValueError("Fixed expenses + goal exceed income")

    # ✅ FIX: Use user's calculated discretionary_breakdown if available
    # This contains the personalized budget based on their spending habits
    discretionary_breakdown = user_answers.get("discretionary_breakdown")

    if discretionary_breakdown:
        # Use user's personalized budget allocation
        flexible_alloc = {
            category: Decimal(str(amount)).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            for category, amount in discretionary_breakdown.items()
        }
    else:
        # Fall back to regional defaults only if no personalized data exists
        category_weights = profile.get(
            "category_weights",
            {
                "food": 0.3,
                "transport": 0.15,
                "entertainment": 0.1,
                "bills": 0.25,
                "savings": 0.2,
            },
        )

        # Normalize weights if needed
        total_weight = sum(category_weights.values())
        if not (0.99 <= total_weight <= 1.01):
            category_weights = {k: v / total_weight for k, v in category_weights.items()}

        # Allocate flexible budget across categories
        flexible_alloc = {
            category: (discretionary * Decimal(str(weight))).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            for category, weight in category_weights.items()
        }

    # Compute total month plan
    full_month_plan = {}
    full_month_plan.update(fixed)
    full_month_plan.update(flexible_alloc)

    # Setup days
    num_days = calendar.monthrange(year, month)[1]
    days = [
        {
            "date": f"{year}-{month:02d}-{day:02d}",
            "planned_budget": {},
            "total": Decimal("0.00"),
        }
        for day in range(1, num_days + 1)
    ]

    # Distribute category amounts across days
    for category, monthly_amount in full_month_plan.items():
        distribute_budget_over_days(days, category, float(monthly_amount))

    # Final cleanup: calculate total per day
    for day in days:
        day["total"] = round(
            sum(Decimal(str(v)) for v in day["planned_budget"].values()), 2
        )

    return days

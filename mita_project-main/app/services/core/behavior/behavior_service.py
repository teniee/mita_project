from datetime import datetime

from app.services.core.behavior.behavioral_config import (
    BEHAVIORAL_BIAS,
    COOLDOWN_DAYS,
)
from app.services.core.behavior.behavioral_budget_allocator import (
    generate_behavioral_distribution as get_behavioral_allocation,
)


def generate_behavioral_calendar(
    start_date: str,
    days: int,
    category_weights: dict,
) -> dict:
    """
    Generates a behavioral spending calendar based on start date and
    category weights.

    Params:
        start_date: str "YYYY-MM-DD"
        days: number of days in the month
        category_weights: {"coffee": 100, "entertainment": 200, ...}

    Returns:
        {1: {"coffee": X, ...}, 2: {...}, ..., 30: {...}}
    """
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    plan = get_behavioral_allocation(
        start_dt,
        days,
        category_weights,
        BEHAVIORAL_BIAS,
        COOLDOWN_DAYS,
    )
    return {i + 1: plan[i] for i in range(days)}

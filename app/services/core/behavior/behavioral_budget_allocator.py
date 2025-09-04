from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from app.services.core.dynamic_threshold_service import (
    get_dynamic_thresholds, ThresholdType, UserContext
)


def get_behavioral_allocation(
    start_date: str, 
    num_days: int, 
    budget_plan: Dict[str, float],
    user_context: Optional[UserContext] = None
) -> List[Dict[str, float]]:
    """Distribute behavioral budget across days using dynamic weekday bias and cooldown.

    :param start_date: Start date in ``YYYY-MM-DD`` format
    :param num_days: Number of days in the period
    :param budget_plan: Category budget, e.g. ``{"groceries": 100.0, "transport": 50.0}``
    :param user_context: User context for dynamic threshold calculation
    :return: List of dictionaries where each element is a day's budget
    """
    # Create default user context if none provided
    if user_context is None:
        user_context = UserContext(
            monthly_income=5000,  # Default middle-income
            age=35,
            region="US",
            family_size=1
        )
    
    # Get dynamic thresholds based on user context
    time_bias_thresholds = get_dynamic_thresholds(ThresholdType.TIME_BIAS, user_context)
    cooldown_thresholds = get_dynamic_thresholds(ThresholdType.COOLDOWN_PERIOD, user_context)
    
    base_date = datetime.strptime(start_date, "%Y-%m-%d")
    calendar = [base_date + timedelta(days=i) for i in range(num_days)]

    memory = defaultdict(list)
    result: List[Dict[str, float]] = [defaultdict(float) for _ in range(num_days)]

    for category, total in budget_plan.items():
        # Use dynamic cooldown based on user context
        cooldown = cooldown_thresholds.get(category, cooldown_thresholds.get(category.replace(" ", "_"), 0))
        
        # Use dynamic time bias based on user context
        bias = time_bias_thresholds.get(category, time_bias_thresholds.get(category.replace(" ", "_"), [1.0] * 7))
        slots = []

        for i, date in enumerate(calendar):
            weekday = date.weekday()
            score = bias[weekday] if weekday < len(bias) else 1.0
            recent_days = memory[category]

            if recent_days and (i - recent_days[-1]) <= cooldown:
                score = 0

            if score > 0:
                slots.append((i, score))

        slots.sort(key=lambda x: -x[1])
        
        # Dynamic slot limitation based on category and user behavior
        if category in ["entertainment", "entertainment events", "clothing", "dining out", "dining_out"]:
            max_slots = 4  # Discretionary spending spread across fewer days
        else:
            max_slots = len(slots)  # Essential spending can be any day
            
        selected = sorted([i for i, _ in slots[:max_slots]])

        if selected:
            amount = round(total / len(selected), 2)
            for i in selected:
                result[i][category] += amount
                memory[category].append(i)

    return [dict(day) for day in result]

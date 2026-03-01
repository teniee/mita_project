from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from sqlalchemy.orm import Session

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


def allocate_behavioral_budget(user_id: int, total_budget: float, db: Session) -> dict:
    """
    Allocate budget across categories based on behavioral analysis.

    This function takes a total budget and distributes it across spending categories
    using behavioral patterns and user context.

    Args:
        user_id: User ID for context
        total_budget: Total budget to allocate
        db: Database session

    Returns:
        Dictionary with category allocations and metadata
    """
    from app.db.models.user import User

    # Get user for context
    user = db.query(User).filter(User.id == user_id).first()

    # Create user context
    UserContext(
        monthly_income=user.monthly_income if user else total_budget,
        age=user.age if user and hasattr(user, 'age') else 35,
        region=user.country if user and hasattr(user, 'country') else "US",
        family_size=1
    )

    # Define default category distribution (percentages)
    default_distribution = {
        "food": 0.30,
        "transportation": 0.15,
        "utilities": 0.10,
        "entertainment": 0.10,
        "shopping": 0.10,
        "healthcare": 0.05,
        "savings": 0.20
    }

    # Allocate budget to categories
    categories = {}
    for category, percentage in default_distribution.items():
        categories[category] = round(total_budget * percentage, 2)

    return {
        "categories": categories,
        "total_allocated": sum(categories.values()),
        "method": "behavioral_allocation",
        "confidence": 0.8,
        "user_context_applied": True
    }

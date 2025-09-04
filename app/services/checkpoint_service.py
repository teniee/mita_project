from statistics import mean
from typing import Any, Dict

from app.services.core.dynamic_threshold_service import (
    get_dynamic_thresholds, ThresholdType, UserContext
)
from app.services.core.income_classification_service import classify_income


def calculate_checkpoint(
    user_profile: Dict[str, Any], transaction_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Calculate a financial checkpoint for the user.

    :param user_profile: dict with user attributes (age, income, etc.)
    :param transaction_data: dict of transactions per category: {"food": [10, 20, 30], ...}
    :return: dict with calculation results
    """

    # 1. Sum per category
    category_totals = {
        category: sum(values)
        for category, values in transaction_data.items()
        if isinstance(values, list) and all(isinstance(v, (int, float)) for v in values)
    }

    # 2. Total amount spent
    total_spent = sum(category_totals.values())

    # 3. Average spend per category
    category_averages = {
        category: round(mean(values), 2)
        for category, values in transaction_data.items()
        if isinstance(values, list) and values
    }

    # 4. Basic behavior assessment
    behavior_score = assess_behavior(user_profile, category_totals)

    # 5. Final response
    return {
        "user_profile": user_profile,
        "total_spent": round(total_spent, 2),
        "category_totals": category_totals,
        "category_averages": category_averages,
        "behavior_score": behavior_score,
        "checkpoint_status": "generated",
    }


def assess_behavior(
    user_profile: Dict[str, Any], category_totals: Dict[str, float]
) -> str:
    """Dynamic behavior analysis using income-appropriate thresholds.

    Uses dynamic thresholds based on user income level and context.
    Returns 'balanced', 'overspending', or 'no_activity'.
    """
    total = sum(category_totals.values())
    if not total:
        return "no_activity"

    # Create user context for dynamic threshold calculation
    monthly_income = user_profile.get('monthly_income', 5000)  # Default if not provided
    age = user_profile.get('age', 35)
    region = user_profile.get('region', 'US')
    
    user_context = UserContext(
        monthly_income=monthly_income,
        age=age,
        region=region,
        family_size=user_profile.get('family_size', 1),
        debt_to_income_ratio=user_profile.get('debt_to_income_ratio', 0.0)
    )
    
    # Get dynamic behavioral trigger thresholds
    behavioral_thresholds = get_dynamic_thresholds(
        ThresholdType.BEHAVIORAL_TRIGGER, user_context
    )
    
    # Get dynamic budget allocation for comparison
    budget_allocations = get_dynamic_thresholds(
        ThresholdType.BUDGET_ALLOCATION, user_context
    )
    
    entertainment = category_totals.get("entertainment", 0)
    dining = category_totals.get("dining out", 0) + category_totals.get("dining", 0)
    
    # Calculate actual percentages
    entertainment_pct = entertainment / total
    dining_pct = dining / total
    
    # Get expected allocations and overspending multipliers
    expected_entertainment = budget_allocations.get('entertainment', 0.08)
    expected_dining = budget_allocations.get('food', 0.12) * 0.5  # Assume 50% of food is dining out
    
    entertainment_threshold = behavioral_thresholds.get('entertainment_overspending', 1.3)
    dining_threshold = behavioral_thresholds.get('food_overspending', 1.25)
    
    # Check if spending exceeds dynamic thresholds
    if (entertainment_pct > expected_entertainment * entertainment_threshold or 
        dining_pct > expected_dining * dining_threshold):
        return "overspending"

    return "balanced"
